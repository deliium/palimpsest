"""Owner-relative replication interpretation and bounded collaboration.

Only the acting owner's retained measurements, delivered speech, and directed
relationship appraisal are used. No peer ledger or objective alignment enters.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.experimentation import HypothesisCondition
from agents.cognition.replication import (
    MAX_COLLABORATIONS,
    MAX_INTERPRETATION_REVISIONS,
    MAX_INTERPRETATIONS,
    REPLICATION_POLICY_VERSION,
    ReplicationCategoricalAppraisal,
    ReplicationCollaboration,
    ReplicationCollaborationAct,
    ReplicationConditionComparison,
    ReplicationError,
    ReplicationInterpretation,
    ReplicationInterpretationRevision,
    ReplicationInvitationStatus,
    ReplicationLedger,
    ReplicationMeasurementBasis,
    ReplicationNoticeCode,
    ReplicationOutboxEntry,
    ReplicationOutboxStatus,
    ReplicationParticipantClaim,
    ReplicationResultReport,
    ReplicationRevisionReason,
    ReplicationSourceAppraisal,
    ReplicationUncertaintyKind,
    default_replication_policy,
    replication_ref,
)
from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.replication_interpretation"
)

_MESSAGE_HEX_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class ReplicationOwnerContext:
    """The acting owner's safe directed source appraisals only."""

    trust_by_entity: tuple[tuple[str, float | None], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.trust_by_entity, tuple):
            raise ReplicationError("replication_invalid_context")
        seen: set[str] = set()
        for entity_id, value in self.trust_by_entity:
            if type(entity_id) is not str or not entity_id or entity_id in seen:
                raise ReplicationError("replication_invalid_context")
            seen.add(entity_id)
            if value is None:
                continue
            if type(value) is not float or not math.isfinite(value):
                raise ReplicationError("replication_invalid_context")
            if not 0.0 <= value <= 1.0:
                raise ReplicationError("replication_invalid_context")

    def normalized_trust(self, entity_id: str | None) -> float | None:
        if entity_id is None:
            return None
        for candidate, value in self.trust_by_entity:
            if candidate == entity_id:
                return value
        return None

    def appraisal_for(
        self, entity_id: str | None
    ) -> ReplicationSourceAppraisal:
        return source_appraisal_for_trust(self.normalized_trust(entity_id))


def source_appraisal_for_trust(
    trust: float | None,
) -> ReplicationSourceAppraisal:
    """Locked subjective thresholds, not source reliability estimates."""

    if trust is None:
        return ReplicationSourceAppraisal.UNKNOWN
    policy = default_replication_policy()
    if trust >= policy.trust_threshold_high:
        return ReplicationSourceAppraisal.TRUSTED_TESTIMONY
    if trust <= policy.trust_threshold_low:
        return ReplicationSourceAppraisal.CONTESTED_TESTIMONY
    return ReplicationSourceAppraisal.UNKNOWN


def _condition_map(
    conditions: tuple[HypothesisCondition, ...],
) -> dict[str, str]:
    return {row.slot.value: row.value_token for row in conditions}


def compare_replication_condition_sets(
    design_conditions: tuple[HypothesisCondition, ...],
    actual_conditions: tuple[HypothesisCondition, ...],
) -> ReplicationConditionComparison:
    """Compare only known slots; incompleteness is never controlled proof."""

    if not design_conditions or not actual_conditions:
        return ReplicationConditionComparison.UNKNOWN
    if _condition_map(design_conditions) == _condition_map(actual_conditions):
        return ReplicationConditionComparison.MATCHED
    return ReplicationConditionComparison.DIFFERENT


def _message_token(
    owner_id: AgentId,
    recipient_entity_id: str,
    message_kind: str,
    design_token: str,
    invitation_token: str | None,
    extra: str = "",
) -> str:
    payload = [
        REPLICATION_POLICY_VERSION,
        owner_id.value,
        recipient_entity_id,
        message_kind,
        design_token,
        invitation_token or "none",
        extra,
    ]
    material = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = hashlib.sha256(material.encode("ascii")).hexdigest()[:_MESSAGE_HEX_LEN]
    return f"rmsg-{digest}"


def _design_prerequisite(
    ledger: ReplicationLedger, design_token: str, recipient_entity_id: str
) -> str | None:
    for entry in ledger.outbox:
        if (
            entry.design_token == design_token
            and entry.recipient_entity_id == recipient_entity_id
            and entry.message_kind == "design"
            and entry.status
            in {
                ReplicationOutboxStatus.PENDING,
                ReplicationOutboxStatus.PROPOSED,
                ReplicationOutboxStatus.ATTEMPTED,
                ReplicationOutboxStatus.DELIVERY_OBSERVED,
                ReplicationOutboxStatus.DELIVERY_UNKNOWN,
            }
        ):
            return entry.message_token
    return None


def _stage_outbox(
    ledger: ReplicationLedger,
    *,
    recipient_entity_id: str,
    message_kind: str,
    design_token: str,
    invitation_token: str | None,
    tick: int,
    extra: str = "",
) -> tuple[ReplicationLedger, str]:
    token = _message_token(
        ledger.owner_id,
        recipient_entity_id,
        message_kind,
        design_token,
        invitation_token,
        extra,
    )
    for entry in ledger.outbox:
        if entry.message_token == token and entry.status not in {
            ReplicationOutboxStatus.CANCELLED,
            ReplicationOutboxStatus.UNSENDABLE,
        }:
            return ledger, "reply_already_staged"
    if len(ledger.outbox) >= 128:
        notice = ReplicationNoticeCode.OUTBOX_CAPACITY
        return (
            replace(ledger, notices=(*ledger.notices, notice))
            if notice not in ledger.notices
            else ledger,
            "outbox_capacity",
        )
    entry = ReplicationOutboxEntry(
        owner_id=ledger.owner_id,
        recipient_entity_id=recipient_entity_id,
        message_kind=message_kind,
        message_token=token,
        design_token=design_token,
        invitation_token=invitation_token,
        prerequisite_message_token=_design_prerequisite(
            ledger, design_token, recipient_entity_id
        ),
        proposed_tick=tick,
    )
    _LOG.debug(
        "replication_reply_staged message_kind=%s outbox_count=%s",
        message_kind,
        len(ledger.outbox) + 1,
    )
    return replace(ledger, outbox=(*ledger.outbox, entry)), "reply_staged"


def open_replication_collaboration(
    ledger: ReplicationLedger, collaboration: ReplicationCollaboration
) -> tuple[ReplicationLedger, str]:
    """Retain one delivered invitation view without inventing a roster."""

    if ledger.owner_id != collaboration.owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if any(
        row.invitation_token == collaboration.invitation_token
        for row in ledger.collaborations
    ):
        return ledger, "duplicate_collaboration"
    if len(ledger.collaborations) >= MAX_COLLABORATIONS:
        notice = ReplicationNoticeCode.COLLABORATION_CAPACITY
        updated = (
            replace(ledger, notices=(*ledger.notices, notice))
            if notice not in ledger.notices
            else ledger
        )
        return updated, "collaboration_capacity"
    _LOG.info(
        "replication_collaboration_opened status=%s collaboration_count=%s",
        collaboration.status.value,
        len(ledger.collaborations) + 1,
    )
    return (
        replace(ledger, collaborations=(*ledger.collaborations, collaboration)),
        "collaboration_opened",
    )


def _find_collaboration(
    ledger: ReplicationLedger, invitation_token: str
) -> ReplicationCollaboration | None:
    for row in ledger.collaborations:
        if row.invitation_token == invitation_token:
            return row
    return None


def stage_replication_participation(
    ledger: ReplicationLedger,
    invitation_token: str,
    *,
    actor_entity_id: str,
    act: ReplicationCollaborationAct,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    """Stage one attributed participate/decline reply to the verified inviter."""

    if act is ReplicationCollaborationAct.INVITE:
        return ledger, "invalid_participation_act"
    collaboration = _find_collaboration(ledger, invitation_token)
    if collaboration is None:
        return ledger, "collaboration_missing"
    if collaboration.status is not ReplicationInvitationStatus.PENDING:
        return ledger, "invitation_not_pending"
    claim_token = replication_ref(
        "rpart", ledger.owner_id.value, actor_entity_id, act.value, tick
    )
    if any(
        claim.claim_token == claim_token for claim in collaboration.participants
    ):
        return ledger, "reply_already_staged"
    claim = ReplicationParticipantClaim(
        actor_entity_id=actor_entity_id,
        act=act,
        tick=tick,
        claim_token=claim_token,
    )
    status = (
        ReplicationInvitationStatus.DECLINED
        if act is ReplicationCollaborationAct.DECLINE
        else ReplicationInvitationStatus.ACCEPTED
    )
    updated_collaboration = replace(
        collaboration,
        status=status,
        participants=(*collaboration.participants, claim),
    )
    collaborations = tuple(
        updated_collaboration
        if row.invitation_token == invitation_token
        else row
        for row in ledger.collaborations
    )
    ledger = replace(ledger, collaborations=collaborations)
    message_kind = (
        "participate"
        if status is ReplicationInvitationStatus.ACCEPTED
        else "decline"
    )
    ledger, reason = _stage_outbox(
        ledger,
        recipient_entity_id=collaboration.inviter_entity_id,
        message_kind=message_kind,
        design_token=collaboration.design_token,
        invitation_token=collaboration.invitation_token,
        tick=tick,
    )
    return ledger, reason


def stage_replication_result_reply(
    ledger: ReplicationLedger,
    invitation_token: str,
    report_token: str,
    *,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    """Stage one result reply to the same verified inviter."""

    collaboration = _find_collaboration(ledger, invitation_token)
    if collaboration is None:
        return ledger, "collaboration_missing"
    reports = [row for row in ledger.reports if row.report_token == report_token]
    if not reports:
        return ledger, "report_missing"
    report = reports[0]
    if report.design_token != collaboration.design_token:
        return ledger, "design_mismatch"
    if report.measurement.basis is not ReplicationMeasurementBasis.OWN_OBSERVATION:
        return ledger, "result_not_own_observation"
    if collaboration.status not in {
        ReplicationInvitationStatus.ACCEPTED,
        ReplicationInvitationStatus.ATTEMPTED,
        ReplicationInvitationStatus.COMPLETED,
    }:
        return ledger, "invitation_not_pending"
    updated = replace(
        collaboration, status=ReplicationInvitationStatus.COMPLETED
    )
    collaborations = tuple(
        updated if row.invitation_token == invitation_token else row
        for row in ledger.collaborations
    )
    ledger = replace(ledger, collaborations=collaborations)
    return _stage_outbox(
        ledger,
        recipient_entity_id=collaboration.inviter_entity_id,
        message_kind="result",
        design_token=collaboration.design_token,
        invitation_token=collaboration.invitation_token,
        tick=tick,
        extra=report.report_token,
    )


def stage_replication_interpretation_reply(
    ledger: ReplicationLedger,
    invitation_token: str,
    interpretation_token: str,
    *,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    """Stage one changed-interpretation reply to the verified inviter."""

    collaboration = _find_collaboration(ledger, invitation_token)
    if collaboration is None:
        return ledger, "collaboration_missing"
    rows = [
        row
        for row in ledger.interpretations
        if row.interpretation_token == interpretation_token
    ]
    if not rows:
        return ledger, "interpretation_missing"
    interpretation = rows[0]
    if interpretation.design_token != collaboration.design_token:
        return ledger, "design_mismatch"
    extra = f"{interpretation_token}:{len(interpretation.revisions)}"
    return _stage_outbox(
        ledger,
        recipient_entity_id=collaboration.inviter_entity_id,
        message_kind="interpret",
        design_token=collaboration.design_token,
        invitation_token=collaboration.invitation_token,
        tick=tick,
        extra=extra,
    )


def _baseline_report(
    ledger: ReplicationLedger, report: ReplicationResultReport
) -> ReplicationResultReport | None:
    candidates = [
        row
        for row in ledger.reports
        if row.design_token == report.design_token
        and row.source_trial_token == report.source_trial_token
        and row.origin_report_token != report.origin_report_token
        and row.measurement.outcome is not None
    ]
    candidates.sort(
        key=lambda row: (
            0
            if row.measurement.basis is ReplicationMeasurementBasis.OWN_OBSERVATION
            else 1,
            row.report_token,
        )
    )
    return candidates[0] if candidates else None


def _appraise(
    design_conditions: tuple[HypothesisCondition, ...],
    report: ReplicationResultReport,
    baseline: ReplicationResultReport | None,
) -> tuple[ReplicationCategoricalAppraisal, ReplicationConditionComparison]:
    actual = report.reported_conditions or report.observed_conditions
    comparison = compare_replication_condition_sets(design_conditions, actual)
    if comparison is ReplicationConditionComparison.UNKNOWN:
        return ReplicationCategoricalAppraisal.INCONCLUSIVE, comparison
    if comparison is ReplicationConditionComparison.DIFFERENT:
        return ReplicationCategoricalAppraisal.NOT_COMPARABLE, comparison
    if (
        baseline is None
        or report.measurement.outcome is None
        or baseline.measurement.outcome is None
    ):
        return ReplicationCategoricalAppraisal.INCONCLUSIVE, comparison
    if baseline.measurement.outcome is report.measurement.outcome:
        return ReplicationCategoricalAppraisal.COMPATIBLE, comparison
    return ReplicationCategoricalAppraisal.CONFLICTING, comparison


def interpret_replication_evidence(
    owner_id: AgentId,
    ledger: ReplicationLedger,
    source_context: ReplicationOwnerContext,
    *,
    tick: int = 0,
) -> tuple[ReplicationLedger, str]:
    """Interpret retained reports with the owner's own social appraisal."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if ledger.owner_id != owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if type(source_context) is not ReplicationOwnerContext:
        raise ReplicationError("replication_invalid_context")
    if not ledger.reports:
        return ledger, "no_reports"
    designs = {row.design_token: row for row in ledger.designs}
    interpretations = {row.interpretation_token: row for row in ledger.interpretations}
    updated_rows = list(ledger.interpretations)
    changed = False
    for report in ledger.reports:
        design = designs.get(report.design_token)
        design_conditions = () if design is None else design.conditions
        appraisal, comparison = _appraise(
            design_conditions, report, _baseline_report(ledger, report)
        )
        source = (
            ReplicationSourceAppraisal.OWN_OBSERVATION
            if report.measurement.basis is ReplicationMeasurementBasis.OWN_OBSERVATION
            else source_context.appraisal_for(report.source_entity_id)
        )
        uncertainty = (
            report.measurement.uncertainty_kind
            is ReplicationUncertaintyKind.UNREPORTED
        )
        token = replication_ref(
            "rint", owner_id.value, report.design_token, report.report_token
        )
        existing = interpretations.get(token)
        if existing is None:
            if len(updated_rows) >= MAX_INTERPRETATIONS:
                notice = ReplicationNoticeCode.INTERPRETATION_CAPACITY
                if notice not in ledger.notices:
                    ledger = replace(ledger, notices=(*ledger.notices, notice))
                continue
            revision = ReplicationInterpretationRevision(
                revision_index=0,
                tick=tick,
                reason=ReplicationRevisionReason.EVIDENCE_ADDED,
                appraisal=appraisal,
                condition_comparison=comparison,
                source_appraisal=source,
                uncertainty_notice=uncertainty,
            )
            row = ReplicationInterpretation(
                owner_id=owner_id,
                interpretation_token=token,
                design_token=report.design_token,
                report_tokens=(report.report_token,),
                appraisal=appraisal,
                condition_comparison=comparison,
                source_appraisal=source,
                uncertainty_notice=uncertainty,
                created_tick=tick,
                revisions=(revision,),
            )
            updated_rows.append(row)
            interpretations[token] = row
            changed = True
            continue
        if (
            existing.appraisal is appraisal
            and existing.condition_comparison is comparison
            and existing.source_appraisal is source
            and existing.uncertainty_notice is uncertainty
        ):
            continue
        reason = (
            ReplicationRevisionReason.SOURCE_REAPPRAISED
            if existing.source_appraisal is not source
            else (
                ReplicationRevisionReason.UNCERTAINTY_NOTED
                if existing.uncertainty_notice is not uncertainty
                else ReplicationRevisionReason.EVIDENCE_ADDED
            )
        )
        if len(existing.revisions) >= MAX_INTERPRETATION_REVISIONS:
            if ReplicationNoticeCode.INTERPRETATION_CAPACITY not in ledger.notices:
                ledger = replace(
                    ledger,
                    notices=(
                        *ledger.notices,
                        ReplicationNoticeCode.INTERPRETATION_CAPACITY,
                    ),
                )
            continue
        revision = ReplicationInterpretationRevision(
            revision_index=len(existing.revisions),
            tick=tick,
            reason=reason,
            appraisal=appraisal,
            condition_comparison=comparison,
            source_appraisal=source,
            uncertainty_notice=uncertainty,
        )
        row = replace(
            existing,
            appraisal=appraisal,
            condition_comparison=comparison,
            source_appraisal=source,
            uncertainty_notice=uncertainty,
            revisions=(*existing.revisions, revision),
        )
        updated_rows = [
            row if candidate.interpretation_token == token else candidate
            for candidate in updated_rows
        ]
        interpretations[token] = row
        changed = True
    if not changed:
        return ledger, "interpretations_unchanged"
    _LOG.info("replication_interpretations_updated count=%s", len(updated_rows))
    return replace(ledger, interpretations=tuple(updated_rows)), (
        "interpretations_updated"
    )


__all__ = [
    "ReplicationOwnerContext",
    "compare_replication_condition_sets",
    "interpret_replication_evidence",
    "open_replication_collaboration",
    "source_appraisal_for_trust",
    "stage_replication_interpretation_reply",
    "stage_replication_participation",
    "stage_replication_result_reply",
]
