"""Compile one receiver-owned ordinary ``Experiment`` from delivered designs.

Designs and invitations are testimony. Only this compiler turns a locally
accepted request into a detached candidate; submission and admission stay with
the ordinary runtime and WorldEngine.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.experimentation import (
    ExperimentCompile,
    ExperimentLedger,
    HypothesisSourceKind,
    compile_scientific_test,
    formulate_hypothesis,
)
from agents.cognition.replication import (
    ExperimentDesign,
    ReplicationAttempt,
    ReplicationAttemptState,
    ReplicationCollaboration,
    ReplicationCollaborationAct,
    ReplicationError,
    ReplicationInvitationStatus,
    ReplicationLedger,
    ReplicationSourceAppraisal,
    replication_attempt_token,
)
from agents.cognition.replication_designs import (
    bind_replication_design,
    replication_ref,
)
from agents.cognition.replication_interpretation import (
    ReplicationOwnerContext,
    stage_replication_participation,
)
from agents.models import AgentId
from world.experimentation import ExperimentOutcomeClass

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.replication_actions"
)

_UNRESOLVED_STATES: Final[frozenset[ReplicationAttemptState]] = frozenset(
    {
        ReplicationAttemptState.PLANNED,
        ReplicationAttemptState.PROPOSED,
        ReplicationAttemptState.UNRESOLVED,
    }
)


@dataclass(frozen=True, slots=True)
class ReplicationCompile:
    """Detached candidate ledgers plus one ordinary Experiment or a reason."""

    replication_ledger: ReplicationLedger
    experiment_ledger: ExperimentLedger
    command: object | None = None
    attempt_token: str | None = None
    reason: str | None = None


def protected_replication_hypothesis_ids(ledger: ReplicationLedger) -> frozenset[str]:
    """Protect hypotheses referenced by unresolved attempts and source drafts."""

    protected = {
        row.hypothesis_id
        for row in ledger.attempts
        if row.state in _UNRESOLVED_STATES
    }
    protected.update(row.hypothesis_id for row in ledger.source_drafts)
    return frozenset(protected)


def replication_local_hypothesis_id(
    owner_id: AgentId,
    design: ExperimentDesign,
    operand_a_id: str,
    operand_b_id: str | None,
) -> str:
    """Namespace the design and concrete binding; never reuse source identity."""

    material = "\x1f".join(
        (
            "scientific-replication.v1",
            owner_id.value,
            design.design_token,
            operand_a_id,
            operand_b_id or "none",
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]
    return f"rpl:{digest}"


def request_replication(
    ledger: ReplicationLedger,
    design_token: str,
    *,
    actor_entity_id: str,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    """Record an explicit owner-local intent without a delivered invitation."""

    design = next(
        (row for row in ledger.designs if row.design_token == design_token), None
    )
    if design is None:
        return ledger, "unknown_design"
    for row in ledger.collaborations:
        if row.design_token == design_token and row.requested:
            return ledger, "request_exists"
    invitation_token = replication_ref(
        "rinv",
        ledger.owner_id.value,
        "explicit",
        design.design_token,
        design.source_trial_token,
    )
    collaboration = ReplicationCollaboration(
        owner_id=ledger.owner_id,
        invitation_token=invitation_token,
        design_token=design.design_token,
        source_trial_token=design.source_trial_token,
        inviter_entity_id=actor_entity_id,
        created_tick=tick,
        status=ReplicationInvitationStatus.ACCEPTED,
        requested=True,
    )
    _LOG.info("replication_request_recorded design_prefix=%s", design_token[:12])
    return (
        replace(ledger, collaborations=(*ledger.collaborations, collaboration)),
        "request_recorded",
    )


def _attempt_for(
    ledger: ReplicationLedger, collaboration: ReplicationCollaboration
) -> ReplicationAttempt | None:
    for row in ledger.attempts:
        if (
            row.design_token == collaboration.design_token
            and row.collaboration_token == collaboration.invitation_token
        ):
            return row
    return None


def _ready(
    ledger: ReplicationLedger,
    collaboration: ReplicationCollaboration,
    experiment_ledger: ExperimentLedger,
    tick: int,
) -> bool:
    if collaboration.status is not ReplicationInvitationStatus.ACCEPTED:
        return False
    if not any(
        row.design_token == collaboration.design_token for row in ledger.designs
    ):
        return False
    if _attempt_for(ledger, collaboration) is not None:
        return False
    used = sum(1 for row in experiment_ledger.trials if row.tick == tick)
    return used < experiment_ledger.max_trials_per_tick


def _accept_participation(
    ledger: ReplicationLedger,
    collaboration: ReplicationCollaboration,
    *,
    actor_entity_id: str,
    tick: int,
) -> tuple[ReplicationLedger, str]:
    if collaboration.status is not ReplicationInvitationStatus.PENDING:
        return ledger, "already_accepted"
    ledger, reason = stage_replication_participation(
        ledger,
        collaboration.invitation_token,
        actor_entity_id=actor_entity_id,
        act=ReplicationCollaborationAct.PARTICIPATE,
        tick=tick,
    )
    return ledger, reason


def compile_replication_test(
    owner_id: AgentId,
    replication_ledger: ReplicationLedger,
    experiment_ledger: ExperimentLedger,
    observation: object,
    *,
    source_context: ReplicationOwnerContext | None = None,
) -> ReplicationCompile:
    """Select one accepted delivered request and compile its ordinary test."""

    if type(owner_id) is not AgentId:
        raise ReplicationError("replication_invalid_owner")
    if replication_ledger.owner_id != owner_id:
        raise ReplicationError("replication_ledger_owner_mismatch")
    if experiment_ledger.owner_id != owner_id:
        raise ReplicationError("experiment_ledger_owner_mismatch")
    context = source_context or ReplicationOwnerContext()
    tick_raw = getattr(observation, "tick", 0)
    tick = tick_raw if type(tick_raw) is int and tick_raw >= 0 else 0
    body = getattr(getattr(observation, "self_body", None), "entity_id", None)
    actor_entity_id = getattr(body, "value", None)
    if type(actor_entity_id) is not str or not actor_entity_id:
        observer = getattr(observation, "observer_id", None)
        actor_entity_id = getattr(observer, "value", None)
    if type(actor_entity_id) is not str or not actor_entity_id:
        return ReplicationCompile(
            replication_ledger, experiment_ledger, reason="body_identity_missing"
        )
    designs = {row.design_token: row for row in replication_ledger.designs}
    collaborations = sorted(
        replication_ledger.collaborations,
        key=lambda row: (
            row.created_tick,
            row.design_token,
            row.invitation_token,
        ),
    )
    current = replication_ledger
    for collaboration in collaborations:
        if collaboration.status is ReplicationInvitationStatus.PENDING:
            if (
                context.appraisal_for(collaboration.inviter_entity_id)
                is ReplicationSourceAppraisal.CONTESTED_TESTIMONY
            ):
                continue
            current, _reason = _accept_participation(
                current,
                collaboration,
                actor_entity_id=actor_entity_id,
                tick=tick,
            )
            collaboration = next(
                row
                for row in current.collaborations
                if row.invitation_token == collaboration.invitation_token
            )
        if not _ready(current, collaboration, experiment_ledger, tick):
            continue
        design = designs.get(collaboration.design_token)
        if design is None:
            continue
        binding = bind_replication_design(design, observation)
        if binding.binding is None:
            _LOG.debug(
                "replication_test_skipped reason_code=%s", binding.reason
            )
            continue
        if design.predicted_outcome is None:
            continue
        hypothesis_id = replication_local_hypothesis_id(
            owner_id,
            design,
            binding.binding.operand_a_id,
            binding.binding.operand_b_id,
        )
        protected = protected_replication_hypothesis_ids(current) | frozenset(
            {hypothesis_id}
        )
        hypothesis = formulate_hypothesis(
            owner_id=owner_id,
            hypothesis_id=hypothesis_id,
            operator=design.operator,
            operand_a_id=binding.binding.operand_a_id,
            operand_b_id=binding.binding.operand_b_id,
            process_token=design.process_token,
            predicted_outcome=ExperimentOutcomeClass(
                design.predicted_outcome.value
                if hasattr(design.predicted_outcome, "value")
                else design.predicted_outcome
            ),
            conditions=design.conditions,
            source_kind=HypothesisSourceKind.COMMUNICATED,
            source_token=f"design:{design.design_token}",
            created_tick=tick,
        )
        hypothesis = replace(hypothesis, confidence_milli=500)
        from agents.cognition.experimentation import admit_hypothesis

        admitted = admit_hypothesis(
            experiment_ledger,
            hypothesis,
            protected_hypothesis_ids=protected,
        )
        if admitted is experiment_ledger:
            _LOG.warning(
                "replication_test_skipped reason_code=replication_hypothesis_capacity"
            )
            return ReplicationCompile(
                current,
                experiment_ledger,
                reason="replication_hypothesis_capacity",
            )
        compiled: ExperimentCompile = compile_scientific_test(
            owner_id,
            admitted,
            observation,
            hypothesis_id=hypothesis_id,
            formulate_if_missing=False,
            causal_model=None,
            protected_hypothesis_ids=protected,
        )
        if compiled.command is None:
            _LOG.debug(
                "replication_test_skipped reason_code=%s",
                compiled.reason or "no_command",
            )
            continue
        attempt_token = replication_attempt_token(
            owner_id,
            design.design_token,
            design.source_trial_token,
            tick,
            collaboration.invitation_token,
        )
        attempt = ReplicationAttempt(
            owner_id=owner_id,
            attempt_token=attempt_token,
            design_token=design.design_token,
            source_trial_token=design.source_trial_token,
            actor_entity_id=actor_entity_id,
            hypothesis_id=hypothesis_id,
            request_tick=tick,
            collaboration_token=collaboration.invitation_token,
            submission_tick=tick,
            operand_a_id=binding.binding.operand_a_id,
            operand_b_id=binding.binding.operand_b_id,
            observed_conditions=binding.binding.observed_conditions,
            condition_comparison=binding.binding.condition_comparison,
            state=ReplicationAttemptState.PROPOSED,
        )
        updated = replace(
            current,
            attempts=(*current.attempts, attempt),
        )
        _LOG.info(
            "replication_test_proposed operator=%s attempt_count=%s",
            design.operator.value,
            len(updated.attempts),
        )
        return ReplicationCompile(
            updated,
            compiled.ledger,
            command=compiled.command,
            attempt_token=attempt_token,
        )
    return ReplicationCompile(
        current, experiment_ledger, reason="no_replication_request"
    )


def correlate_replication_occurrences(
    owner_id: AgentId,
    replication_ledger: ReplicationLedger,
    experiment_ledger: ExperimentLedger,
    observation: object,
) -> tuple[ReplicationLedger, ExperimentLedger]:
    """Match one actor-visible result to an unresolved local attempt."""

    from agents.cognition.experimentation import (
        ExperimentTrial,
        apply_test_outcome,
        record_trial,
    )
    from agents.cognition.replication import (
        ReplicationMeasurement,
        ReplicationMeasurementBasis,
        ReplicationMeasurementResolution,
        ReplicationUncertaintyKind,
        record_replication_measurement,
    )
    from agents.cognition.replication_designs import replication_ref
    from agents.cognition.replication_interpretation import (
        compare_replication_condition_sets,
    )

    body = getattr(getattr(observation, "self_body", None), "entity_id", None)
    actor = getattr(body, "value", None)
    if type(actor) is not str or not actor:
        return replication_ledger, experiment_ledger
    designs = {row.design_token: row for row in replication_ledger.designs}
    for occurrence in getattr(observation, "occurrences", ()):
        if getattr(occurrence, "kind", None) != "experiment_resolved":
            continue
        facts = getattr(occurrence, "public_facts", {})
        operator = facts.get("operator")
        outcome_text = facts.get("outcome_class")
        if type(operator) is not str or type(outcome_text) is not str:
            continue
        try:
            outcome = ExperimentOutcomeClass(outcome_text)
        except ValueError:
            continue
        provenance = getattr(occurrence, "provenance", None)
        event = getattr(provenance, "source_event_id", None)
        event_id = getattr(event, "value", None)
        source_tick = getattr(provenance, "source_tick", None)
        other = getattr(occurrence, "other_entity_id", None)
        operand = getattr(other, "value", None)
        if type(event_id) is not str or type(source_tick) is not int:
            continue
        matches = []
        for attempt in replication_ledger.attempts:
            design = designs.get(attempt.design_token)
            if design is None or attempt.state is not ReplicationAttemptState.PROPOSED:
                continue
            if attempt.actor_entity_id != actor:
                continue
            if design.operator.value != operator:
                continue
            if attempt.operand_a_id != operand:
                continue
            if attempt.submission_tick != source_tick:
                continue
            matches.append(attempt)
        if len(matches) != 1:
            drafts = [
                draft
                for draft in replication_ledger.source_drafts
                if draft.actor_entity_id == actor
                and draft.created_tick == source_tick
                and draft.operator.value == operator
            ]
            if len(drafts) == 1:
                trial = ExperimentTrial(
                    tick=source_tick,
                    event_id=event_id,
                    outcome_class=outcome.value,
                    discovery_mode="deliberate",
                )
                from agents.cognition.replication import (
                    ReplicationMeasurement as _Measurement,
                )
                from agents.cognition.replication import (
                    ReplicationMeasurementBasis as _Basis,
                )
                from agents.cognition.replication import (
                    ReplicationMeasurementResolution as _Resolution,
                )
                from agents.cognition.replication import (
                    ReplicationResultReport as _Report,
                )
                from agents.cognition.replication import (
                    ReplicationUncertaintyKind as _Uncertainty,
                )
                from agents.cognition.replication_designs import (
                    freeze_source_design_from_draft,
                )

                frozen = freeze_source_design_from_draft(drafts[0], trial)
                if frozen.design is not None:
                    replication_ledger = replace(
                        replication_ledger,
                        designs=(*replication_ledger.designs, frozen.design),
                        source_drafts=tuple(
                            row
                            for row in replication_ledger.source_drafts
                            if row is not drafts[0]
                        ),
                    )
                    origin = replication_ref(
                        "rrep",
                        owner_id.value,
                        drafts[0].hypothesis_id,
                        event_id,
                    )
                    report = _Report(
                        owner_id=owner_id,
                        report_token=replication_ref(
                            "rlrep", owner_id.value, origin, event_id
                        ),
                        origin_report_token=origin,
                        content_digest=hashlib.sha256(
                            f"{origin}|{event_id}".encode()
                        ).hexdigest()[:32],
                        design_token=frozen.design.design_token,
                        attempt_token=replication_ref(
                            "ratt", owner_id.value, event_id
                        ),
                        source_trial_token=frozen.design.source_trial_token,
                        source_root_token=origin,
                        measurement=_Measurement(
                            resolution=_Resolution.OUTCOME_CLASS,
                            uncertainty_kind=_Uncertainty.UNREPORTED,
                            basis=_Basis.OWN_OBSERVATION,
                            outcome=outcome,
                        ),
                        declared_measurement_basis=_Basis.OWN_OBSERVATION,
                        performer_claim_token=replication_ref(
                            "rpart", owner_id.value, actor
                        ),
                        observed_conditions=drafts[0].conditions,
                        reported_conditions=drafts[0].conditions,
                        source_entity_id=actor,
                    )
                    replication_ledger = replace(
                        replication_ledger,
                        reports=(*replication_ledger.reports, report),
                    )
            continue
        attempt = matches[0]
        design = designs[attempt.design_token]
        comparison = compare_replication_condition_sets(
            design.conditions, attempt.observed_conditions
        )
        performer = replication_ref("rpart", owner_id.value, actor)
        replication_ledger, reason = record_replication_measurement(
            replication_ledger,
            attempt.attempt_token,
            measurement=ReplicationMeasurement(
                resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
                uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
                basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
                outcome=outcome,
            ),
            condition_comparison=comparison,
            resolution_event_id=event_id,
            performer_claim_token=performer,
            observed_conditions=attempt.observed_conditions,
            reported_conditions=attempt.observed_conditions,
        )
        if reason != "attempt_transitioned":
            continue
        if attempt.collaboration_token is not None:
            from agents.cognition.replication_interpretation import (
                stage_replication_result_reply,
            )

            report_token = next(
                (
                    row.report_token
                    for row in replication_ledger.reports
                    if row.attempt_token == attempt.attempt_token
                ),
                None,
            )
            if report_token is not None:
                replication_ledger, _reply = stage_replication_result_reply(
                    replication_ledger,
                    attempt.collaboration_token,
                    report_token,
                    tick=source_tick,
                )
        if not any(
            row.event_id == event_id for row in experiment_ledger.trials
        ):
            try:
                experiment_ledger = apply_test_outcome(
                    experiment_ledger,
                    attempt.hypothesis_id,
                    outcome_class=outcome.value,
                    event_id=event_id,
                    tick=source_tick,
                    discovery_mode="deliberate",
                )
                experiment_ledger = record_trial(
                    experiment_ledger,
                    ExperimentTrial(
                        tick=source_tick,
                        event_id=event_id,
                        outcome_class=outcome.value,
                        discovery_mode="deliberate",
                        hypothesis_id=attempt.hypothesis_id,
                    ),
                )
            except (KeyError, ValueError):
                _LOG.warning(
                    "replication_outcome_scoring_skipped reason_code=hypothesis_missing"
                )
        _LOG.info("replication_outcome_correlated outcome_class=%s", outcome.value)
        break
    return replication_ledger, experiment_ledger


__all__ = [
    "ReplicationCompile",
    "compile_replication_test",
    "correlate_replication_occurrences",
    "protected_replication_hypothesis_ids",
    "replication_local_hypothesis_id",
    "request_replication",
]
