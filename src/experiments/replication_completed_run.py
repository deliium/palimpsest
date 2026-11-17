"""Trusted completed-run bridge for detached replication analysis.

Owner ledgers and committed events are normalized once here; analysis never
imports cognition or world authority.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any, Final, cast

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_contract import (
    REPLICATION_POLICY_VERSION,
    ReplicationAnalysis,
)
from analysis.replication_rows import (
    ReplicationAttemptFact,
    ReplicationCollaborationFact,
    ReplicationConditionFact,
    ReplicationDeclarationFact,
    ReplicationDesignFact,
    ReplicationExecutionFact,
    ReplicationFacts,
    ReplicationInterpretationFact,
    ReplicationMeasurementFact,
    ReplicationReportFact,
    ReplicationSelectorFact,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.replication_completed_run"
)

_PREFIX = {
    "design": "rpd",
    "trial": "rpt",
    "execution": "rpe",
    "participant": "rpp",
    "entity": "rpen",
    "hypothesis": "rph",
    "report": "rpr",
    "local_report": "rplr",
    "attempt": "rpa",
    "invitation": "rpi",
    "collaboration": "rpc",
    "origin": "rpo",
    "group": "rpg",
    "delivery": "rpdl",
    "interpretation": "rpin",
}


def _token(run_id: str, namespace: str, reference: str) -> str:
    prefix = _PREFIX.get(namespace)
    if prefix is None:
        raise ValueError("replication_bridge_invalid_namespace")
    material = json.dumps(
        [REPLICATION_POLICY_VERSION, run_id, namespace, reference],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return f"{prefix}-" + hashlib.sha256(material).hexdigest()[:32]


def _conditions(rows: object) -> tuple[ReplicationConditionFact, ...]:
    result = []
    for row in cast(Any, rows):
        token = getattr(row, "value_token", "")
        if getattr(row, "slot", None) is None:
            continue
        result.append(
            ReplicationConditionFact(
                slot=row.slot.value, token=token
            )
        )
    return tuple(sorted(result, key=lambda row: row.slot))


def _selector_tokens(run_id: str, selector: object) -> ReplicationSelectorFact | None:
    if selector is None:
        return None
    exact = getattr(selector, "exact_entity_id", None)
    return ReplicationSelectorFact(
        family=getattr(getattr(selector, "family", None), "value", ""),
        kind=getattr(selector, "kind", ""),
        binding_mode=getattr(getattr(selector, "binding_mode", None), "value", ""),
        exact_entity_token=(
            None if exact is None else _token(run_id, "entity", str(exact))
        ),
    )


def _measurement(run_id: str, measurement: object) -> ReplicationMeasurementFact:
    outcome = getattr(measurement, "outcome", None)
    return ReplicationMeasurementFact(
        outcome=None if outcome is None else outcome.value,
        resolution=getattr(getattr(measurement, "resolution", None), "value", ""),
        uncertainty_kind=getattr(
            getattr(measurement, "uncertainty_kind", None), "value", ""
        ),
        possible_outcomes=tuple(
            sorted(
                item.value
                for item in getattr(measurement, "possible_outcomes", ())
            )
        ),
        basis=getattr(getattr(measurement, "basis", None), "value", ""),
    )


def replication_facts(
    *,
    run_id: str,
    replication_ledgers: Sequence[object],
    events: Sequence[object] = (),
    registered_agent_ids: Sequence[str] = (),
    expected_participants: int = 0,
) -> ReplicationFacts:
    """Normalize completed owner exports and committed events exactly once."""

    designs: dict[str, ReplicationDesignFact] = {}
    attempts = []
    reports = []
    interpretations = []
    collaborations = []
    participant_ids = {str(value) for value in registered_agent_ids}
    for raw_ledger in replication_ledgers:
        ledger = cast(Any, raw_ledger)
        if type(ledger).__name__ != "ReplicationLedger" or not hasattr(
            ledger, "owner_id"
        ):
            raise TypeError("replication_ledgers entries must be replication ledgers")
        participant = _token(run_id, "participant", ledger.owner_id.value)
        participant_ids.add(ledger.owner_id.value)
        for design in ledger.designs:
            selector_a = _selector_tokens(run_id, design.operand_a_selector)
            selector_b = _selector_tokens(run_id, design.operand_b_selector)
            if selector_a is None:
                continue
            designs[design.design_token] = ReplicationDesignFact(
                design_token=_token(run_id, "design", design.design_token),
                source_design_digest=hashlib.sha256(
                    design.design_token.encode("ascii")
                ).hexdigest(),
                origin_token=_token(run_id, "origin", design.origin_token),
                parent_design_token=(
                    None
                    if design.parent_design_token is None
                    else _token(run_id, "design", design.parent_design_token)
                ),
                source_hypothesis_token=_token(
                    run_id, "hypothesis", design.source_hypothesis_token
                ),
                source_trial_token=_token(
                    run_id, "trial", design.source_trial_token
                ),
                created_tick=design.created_tick,
                operator=design.operator.value,
                process_token=design.process_token.value,
                operand_a_selector=selector_a,
                operand_b_selector=selector_b,
                predicted_outcome=(
                    None
                    if design.predicted_outcome is None
                    else design.predicted_outcome.value
                ),
                conditions=_conditions(design.conditions),
            )
        for attempt in ledger.attempts:
            attempts.append(
                ReplicationAttemptFact(
                    attempt_token=_token(run_id, "attempt", attempt.attempt_token),
                    participant_token=participant,
                    design_token=_token(run_id, "design", attempt.design_token),
                    source_trial_token=_token(
                        run_id, "trial", attempt.source_trial_token
                    ),
                    collaboration_token=(
                        None
                        if attempt.collaboration_token is None
                        else _token(
                            run_id, "collaboration", attempt.collaboration_token
                        )
                    ),
                    hypothesis_token=_token(
                        run_id, "hypothesis", attempt.hypothesis_id
                    ),
                    request_tick=attempt.request_tick,
                    submission_tick=attempt.submission_tick,
                    observation_tick=(
                        attempt.submission_tick
                        if attempt.submission_tick is not None
                        else attempt.request_tick
                    ),
                    operand_a_token=(
                        None
                        if attempt.operand_a_id is None
                        else _token(run_id, "entity", attempt.operand_a_id)
                    ),
                    operand_b_token=(
                        None
                        if attempt.operand_b_id is None
                        else _token(run_id, "entity", attempt.operand_b_id)
                    ),
                    condition_snapshot=_conditions(attempt.observed_conditions),
                    condition_comparison=attempt.condition_comparison.value,
                    state=attempt.state.value,
                    result_root_token=None,
                    reason_codes=(),
                )
            )
        for report in ledger.reports:
            reports.append(
                ReplicationReportFact(
                    local_report_token=_token(
                        run_id, "local_report", report.report_token
                    ),
                    origin_report_token=_token(
                        run_id, "report", report.origin_report_token
                    ),
                    participant_token=participant,
                    performer_claim_token=_token(
                        run_id, "entity", report.performer_claim_token
                    ),
                    design_token=_token(run_id, "design", report.design_token),
                    attempt_token=_token(run_id, "attempt", report.attempt_token),
                    source_trial_token=_token(
                        run_id, "trial", report.source_trial_token
                    ),
                    result_root_token=_token(run_id, "trial", report.source_root_token),
                    report_tick=0,
                    measurement=_measurement(run_id, report.measurement),
                    declared_measurement_basis=(
                        report.declared_measurement_basis.value
                    ),
                    condition_snapshot=_conditions(report.reported_conditions),
                    collaboration_token=(
                        None
                        if report.collaboration_claim_token is None
                        else _token(
                            run_id,
                            "collaboration",
                            report.collaboration_claim_token,
                        )
                    ),
                    delivery_token=(
                        None
                        if report.delivery_event_id is None
                        else _token(
                            run_id, "delivery", report.delivery_event_id
                        )
                    ),
                    provenance_kind=report.measurement.basis.value,
                    claim_digest=report.content_digest,
                )
            )
        for interpretation in ledger.interpretations:
            for revision in interpretation.revisions or (
                None,
            ):
                index = 0 if revision is None else revision.revision_index
                tick = 0 if revision is None else revision.tick
                interpretations.append(
                    ReplicationInterpretationFact(
                        interpretation_token=_token(
                            run_id,
                            "interpretation",
                            f"{ledger.owner_id.value}:{interpretation.interpretation_token}:{index}",
                        ),
                        participant_token=participant,
                        design_token=_token(
                            run_id, "design", interpretation.design_token
                        ),
                        origin_report_token=_token(
                            run_id,
                            "report",
                            interpretation.report_tokens[0],
                        ),
                        local_report_token=_token(
                            run_id,
                            "local_report",
                            interpretation.report_tokens[0],
                        ),
                        invitation_token=None,
                        collaboration_token=None,
                        revision_index=index,
                        revision_tick=tick,
                        appraisal=interpretation.appraisal.value,
                        condition_comparison=(
                            interpretation.condition_comparison.value
                        ),
                        source_appraisal=interpretation.source_appraisal.value,
                        uncertainty_notice=(
                            "unreported"
                            if interpretation.uncertainty_notice
                            else "none"
                        ),
                        reason_codes=(),
                    )
                )
        for collaboration in ledger.collaborations:
            collaboration_token = _token(
                run_id, "collaboration", collaboration.invitation_token
            )
            collaborations.append(
                ReplicationCollaborationFact(
                    collaboration_token=collaboration_token,
                    participant_token=participant,
                    invitation_token=_token(
                        run_id, "invitation", collaboration.invitation_token
                    ),
                    design_token=_token(
                        run_id, "design", collaboration.design_token
                    ),
                    source_trial_token=_token(
                        run_id, "trial", collaboration.source_trial_token
                    ),
                    inviter_token=_token(
                        run_id, "entity", collaboration.inviter_entity_id
                    ),
                    group_claim_token=(
                        None
                        if collaboration.group_claim_token is None
                        else _token(
                            run_id, "group", collaboration.group_claim_token
                        )
                    ),
                    status=collaboration.status.value,
                    created_tick=collaboration.created_tick,
                    updated_tick=collaboration.created_tick,
                    participant_declarations=tuple(
                        ReplicationDeclarationFact(
                            participant_token=_token(
                                run_id, "participant", claim.actor_entity_id
                            ),
                            act=claim.act.value,
                            tick=claim.tick,
                            delivery_token=None,
                        )
                        for claim in collaboration.participants
                    ),
                )
            )
    executions = []
    for event in events:
        details = getattr(event, "details", None)
        if details is None or getattr(details, "kind", None) != "experiment_resolved":
            continue
        actor = getattr(getattr(event, "actor_id", None), "value", None)
        event_id = getattr(getattr(event, "event_id", None), "value", None)
        if type(actor) is not str or type(event_id) is not str:
            continue
        executions.append(
            ReplicationExecutionFact(
                execution_token=_token(run_id, "execution", event_id),
                result_root_token=_token(
                    run_id,
                    "trial",
                    __import__(
                        "agents.cognition.replication_designs",
                        fromlist=["replication_ref"],
                    ).replication_ref("rtrl", actor, event_id),
                ),
                participant_token=_token(run_id, "participant", actor),
                execution_tick=getattr(event, "tick", 0),
                operator=details.operator,
                process_token=details.process_token,
                operand_a_token=_token(
                    run_id, "entity", details.operand_a_id.value
                ),
                operand_b_token=(
                    None
                    if details.operand_b_id is None
                    else _token(run_id, "entity", details.operand_b_id.value)
                ),
                outcome=details.outcome_class,
            )
        )
    notices = []
    if expected_participants and len(participant_ids) < expected_participants:
        notices.append("partial_owner_export")
    return ReplicationFacts(
        designs=tuple(designs.values()),
        attempts=tuple(attempts),
        executions=tuple(executions),
        reports=tuple(reports),
        interpretations=tuple(interpretations),
        collaborations=tuple(collaborations),
        notices=tuple(notices),
    )


def build_completed_run_replication_analysis(
    *,
    run_id: str,
    replication_ledgers: Sequence[object],
    events: Sequence[object] = (),
    registered_agent_ids: Sequence[str] = (),
    expected_participants: int = 0,
) -> ReplicationAnalysis:
    facts = replication_facts(
        run_id=run_id,
        replication_ledgers=replication_ledgers,
        events=events,
        registered_agent_ids=registered_agent_ids,
        expected_participants=expected_participants,
    )
    return harvest_replication_analysis(facts)


__all__ = ["build_completed_run_replication_analysis", "replication_facts"]
