"""Hand-computed collective-decision metric families and denominators."""

from __future__ import annotations

from agents.cognition.collective_decisions import (
    CollectiveAct,
    CollectiveCompliance,
    CollectiveComplianceStatus,
    CollectiveDecisionLedger,
    CollectiveDelegation,
    CollectiveEvidence,
    CollectiveEvidenceChannel,
    CollectiveExecutionStatus,
    CollectiveInfluence,
    CollectiveInfluenceKind,
    CollectiveOutcome,
    CollectiveOutcomeKind,
    CollectivePosition,
    CollectivePositionStance,
    CollectiveProposal,
    CollectiveProposalStatus,
    CollectiveTopic,
    collective_decision_evidence_id,
    collective_proposal_id,
    collective_proposal_ref,
)
from agents.models import AgentId
from analysis.collective_decisions import (
    harvest_collective_decision_rows,
    harvest_collective_decision_snapshot,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability

_ADA = AgentId("ada")
_BEN = AgentId("ben")
_CONTEXT = "a" * 16


def _proposal(
    owner: AgentId,
    *,
    topic: CollectiveTopic,
    action: str,
    status: CollectiveProposalStatus = CollectiveProposalStatus.ACTIVE,
) -> CollectiveProposal:
    ref = collective_proposal_ref(
        owner,
        originator_id=_BEN,
        topic=topic,
        context_key=_CONTEXT,
        inception_tick=1,
        inception_lineage=f"metric-{action}",
    )
    evidence = CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            ref, 0, CollectiveEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=CollectiveEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=1,
    )
    return CollectiveProposal(
        proposal_id=collective_proposal_id(owner, ref, 0),
        owner_id=owner,
        proposal_ref=ref,
        revision=0,
        topic=topic,
        context_key=_CONTEXT,
        action_token=action,
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=12,
        status=status,
        originator_id=_BEN,
        evidence=(evidence,),
    )


def _position(
    owner: AgentId,
    proposal: CollectiveProposal,
    *,
    actor: AgentId,
    stance: CollectivePositionStance = CollectivePositionStance.SUPPORT,
    active: bool = True,
    channel: CollectiveEvidenceChannel = CollectiveEvidenceChannel.COMMUNICATED,
    tick: int = 2,
) -> CollectivePosition:
    import hashlib

    position_id = hashlib.sha256(
        f"{owner.value}|{actor.value}|{tick}|{stance.value}".encode()
    ).hexdigest()
    return CollectivePosition(
        position_id=position_id,
        actor_id=actor,
        proposal_ref=proposal.proposal_ref,
        revision=proposal.revision,
        stance=stance,
        strength=0.6,
        channel=channel,
        root_ref=f"root-{actor.value}-{tick}",
        independently_evidenced=True,
        first_tick=tick,
        last_tick=tick,
        evidence_id="e" * 64,
        active=active,
    )


def _decision(owner: AgentId = _ADA) -> CollectiveDecisionLedger:
    proposal = _proposal(
        owner, topic=CollectiveTopic.COLLECTIVE_PROJECT, action="start_project"
    )
    positions = (
        _position(
            owner,
            proposal,
            actor=owner,
            channel=CollectiveEvidenceChannel.OBSERVED,
        ),
        _position(owner, proposal, actor=_BEN, tick=3),
    )
    delegation = CollectiveDelegation(
        delegation_id="a" * 64,
        delegator_id=owner,
        delegate_id=_ADA if owner == _BEN else _BEN,
        proposal_ref=proposal.proposal_ref,
        revision=0,
        strength=0.5,
        first_tick=2,
        last_tick=2,
        expires_tick=9,
        evidence_id="b" * 64,
    )
    outcome = CollectiveOutcome(
        outcome_id="c" * 64,
        proposal_ref=proposal.proposal_ref,
        revision=0,
        kind=CollectiveOutcomeKind.CLAIMED,
        execution_status=CollectiveExecutionStatus.UNKNOWN,
        claimed=True,
        first_tick=4,
        last_tick=4,
        actor_id=owner,
    )
    compliance = (
        CollectiveCompliance(
            compliance_id="d" * 64,
            actor_id=owner,
            proposal_ref=proposal.proposal_ref,
            revision=0,
            status=CollectiveComplianceStatus.MATCHED,
            window_first_tick=1,
            window_last_tick=4,
            observed_action_token="start_project",
            tick=4,
        ),
        CollectiveCompliance(
            compliance_id="e" * 64,
            actor_id=_BEN,
            proposal_ref=proposal.proposal_ref,
            revision=0,
            status=CollectiveComplianceStatus.CONTRARY,
            window_first_tick=1,
            window_last_tick=4,
            observed_action_token="damaged",
            tick=4,
        ),
        CollectiveCompliance(
            compliance_id="f" * 64,
            actor_id=owner,
            proposal_ref=proposal.proposal_ref,
            revision=0,
            status=CollectiveComplianceStatus.UNKNOWN,
            window_first_tick=1,
            window_last_tick=12,
            tick=4,
        ),
    )
    influence = (
        CollectiveInfluence(
            influence_id="1" * 64,
            proposal_ref=proposal.proposal_ref,
            revision=0,
            source_act=CollectiveAct.SUPPORT,
            kind=CollectiveInfluenceKind.PREFERENCE_CHANGED,
            strength=0.4,
            tick=3,
        ),
        CollectiveInfluence(
            influence_id="2" * 64,
            proposal_ref=proposal.proposal_ref,
            revision=0,
            source_act=CollectiveAct.COORDINATE,
            kind=CollectiveInfluenceKind.UNAVAILABLE,
            strength=0.0,
            tick=3,
            unavailable_reason="no_comparator",
        ),
    )
    return CollectiveDecisionLedger(
        owner_id=owner,
        proposals=(proposal,),
        positions=positions,
        delegations=(delegation,),
        outcomes=(outcome,),
        compliance=compliance,
        influence=influence,
        first_observed_tick=1,
        last_observed_tick=4,
        observation_count=4,
    )


def test_metric_service_connects_collective_rows_to_all_three_families() -> None:
    rows = harvest_collective_decision_rows((_decision(),))
    inputs = MetricComputationInputs(
        run_id="run-metrics",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=rows,
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    by_family = {document.metric_family: document for document in documents}
    process = by_family["collective_decision_process"]
    outcomes = by_family["collective_decision_outcomes"]
    disagreement = by_family["collective_decision_disagreement"]
    assert process.values["proposal_count"] == 1
    assert process.values["direct_position_count"] == 1
    assert process.values["reported_position_count"] == 1
    assert process.values["delegation_count"] == 1
    assert process.values["coordination_count"] == 1
    assert process.values["preference_changed_count"] == 1
    assert process.values["unavailable_attribution_count"] == 1
    assert process.availability is MetricAvailability.PRESENT
    assert outcomes.values["claimed_count"] == 1
    assert outcomes.values["matched_count"] == 1
    assert outcomes.values["contrary_count"] == 1
    assert outcomes.values["compliance_denominator"] == 2
    assert outcomes.values["unknown_count"] == 1
    assert outcomes.values["censored_count"] == 1
    assert disagreement.availability is MetricAvailability.PRESENT
    assert disagreement.values["within_owner_contradiction_count"] == 0
    assert disagreement.values["aligned_course_count"] == 0
    assert disagreement.values["excluded_alignment_count"] == 0


def test_disabled_inputs_have_explicit_absence() -> None:
    inputs = MetricComputationInputs(
        run_id="run-metrics-off",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=(),
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    by_family = {document.metric_family: document for document in documents}
    for family in (
        "collective_decision_process",
        "collective_decision_outcomes",
        "collective_decision_disagreement",
    ):
        assert by_family[family].availability is MetricAvailability.ABSENT


def test_enabled_empty_selection_is_not_a_fabricated_zero_for_outcomes() -> None:
    snapshot = harvest_collective_decision_snapshot(
        CollectiveDecisionLedger(owner_id=_ADA)
    )
    inputs = MetricComputationInputs(
        run_id="run-metrics-empty",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=(snapshot,),
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    by_family = {document.metric_family: document for document in documents}
    assert by_family["collective_decision_process"].availability is (
        MetricAvailability.PRESENT
    )
    assert by_family["collective_decision_outcomes"].availability is (
        MetricAvailability.ABSENT
    )


def test_pruned_history_marks_partial_coverage() -> None:
    ledger = _decision()
    pruned = CollectiveDecisionLedger(
        owner_id=ledger.owner_id,
        proposals=ledger.proposals,
        positions=ledger.positions,
        delegations=ledger.delegations,
        outcomes=ledger.outcomes,
        compliance=ledger.compliance,
        influence=ledger.influence,
        first_observed_tick=1,
        last_observed_tick=4,
        observation_count=4,
        pruned_evidence_count=2,
    )
    snapshot = harvest_collective_decision_snapshot(pruned)
    assert snapshot.coverage == "partial"
    inputs = MetricComputationInputs(
        run_id="run-metrics-partial",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=(snapshot,),
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    by_family = {document.metric_family: document for document in documents}
    assert by_family["collective_decision_process"].values["partial_coverage"] is True
    assert by_family["collective_decision_process"].availability is (
        MetricAvailability.PARTIAL
    )


def test_cross_owner_disagreement_uses_aligned_courses_only() -> None:
    ada = _decision(_ADA)
    ben = _decision(_BEN)
    ben = CollectiveDecisionLedger(
        owner_id=_BEN,
        proposals=ben.proposals,
        positions=(
            _position(
                _BEN,
                ben.proposals[0],
                actor=_BEN,
                stance=CollectivePositionStance.OPPOSE,
            ),
        ),
        first_observed_tick=1,
        last_observed_tick=4,
        observation_count=4,
    )
    rows = harvest_collective_decision_rows((ada, ben))
    inputs = MetricComputationInputs(
        run_id="run-metrics-disagreement",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=rows,
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    by_family = {document.metric_family: document for document in documents}
    disagreement = by_family["collective_decision_disagreement"]
    assert disagreement.values["aligned_course_count"] == 1
    assert disagreement.values["cross_owner_disagreement_count"] == 1
    assert disagreement.values["excluded_alignment_count"] == 0


def test_objective_effects_join_supported_courses_without_legitimacy() -> None:
    from analysis.collective_decisions import (
        CollectiveEffectRow,
        match_collective_effects,
    )

    rows = harvest_collective_decision_rows((_decision(),))
    matching = CollectiveEffectRow(
        actor_id="ada", kind="collective_project_started", tick=3
    )
    wrong_actor = CollectiveEffectRow(
        actor_id="carol", kind="collective_project_started", tick=3
    )
    wrong_window = CollectiveEffectRow(
        actor_id="ada", kind="collective_project_started", tick=40
    )
    wrong_kind = CollectiveEffectRow(actor_id="ada", kind="gave", tick=3)
    matches = match_collective_effects(
        rows, (matching, wrong_actor, wrong_window, wrong_kind)
    )
    assert len(matches) == 1
    assert matches[0].actor_id == "ada"
    assert matches[0].kind == "collective_project_started"
    inputs = MetricComputationInputs(
        run_id="run-metrics-effects",
        input_revision="rev-1",
        window_end=4,
        collective_decision_rows=rows,
        collective_decision_effects=(matching, wrong_actor, wrong_window),
    )
    bundle = assemble_metric_documents(inputs)
    documents = bundle.documents
    outcomes = next(
        item
        for item in documents
        if item.metric_family == "collective_decision_outcomes"
    )
    assert outcomes.values["objective_effect_count"] == 3
    assert outcomes.values["objective_matched_count"] == 1
    speech_only = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-metrics-speech-only",
            input_revision="rev-1",
            window_end=4,
            collective_decision_rows=rows,
        )
    ).documents
    outcomes = next(
        item
        for item in speech_only
        if item.metric_family == "collective_decision_outcomes"
    )
    assert outcomes.values["objective_matched_count"] == 0
