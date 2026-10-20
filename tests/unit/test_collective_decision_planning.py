"""Bounded collective-decision behavior, influence attribution, and adapters."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.collective_decision_actions import (
    COLLECTIVE_TOPIC_COMMANDS,
    collective_decision_allowed_command,
    collective_decision_execution_status,
)
from agents.cognition.collective_decisions import (
    CollectiveAct,
    CollectiveComplianceStatus,
    CollectiveDecisionLedger,
    CollectiveEvidence,
    CollectiveEvidenceChannel,
    CollectiveExecutionStatus,
    CollectiveInfluenceKind,
    CollectivePosition,
    CollectivePositionStance,
    CollectiveProposal,
    CollectiveProposalStatus,
    CollectiveTopic,
    classify_collective_decision_influence,
    collective_decision_direction_preference,
    collective_decision_evidence_id,
    collective_decision_topic_direction,
    collective_proposal_id,
    collective_proposal_ref,
)
from agents.cognition.models import ActionDirection
from agents.models import AgentId
from world.actions import (
    ContributeCollectiveProject,
    Give,
    Move,
    OpposePublicGood,
    StartCollectiveProject,
    Store,
    Talk,
    Wait,
)
from world.identifiers import EntityId

_OWNER = AgentId("ada")
_OTHER = AgentId("bob")
_CONTEXT = "a" * 16


def _proposal(
    *,
    topic: CollectiveTopic = CollectiveTopic.COLLECTIVE_PROJECT,
    status: CollectiveProposalStatus = CollectiveProposalStatus.ACTIVE,
    window_last: int = 20,
    originator: AgentId = _OTHER,
) -> CollectiveProposal:
    ref = collective_proposal_ref(
        _OWNER,
        originator_id=originator,
        topic=topic,
        context_key=_CONTEXT,
        inception_tick=1,
        inception_lineage="planning",
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
        proposal_id=collective_proposal_id(_OWNER, ref, 0),
        owner_id=_OWNER,
        proposal_ref=ref,
        revision=0,
        topic=topic,
        context_key=_CONTEXT,
        action_token="start_project",
        first_tick=1,
        last_tick=1,
        window_first_tick=1,
        window_last_tick=window_last,
        status=status,
        originator_id=originator,
        evidence=(evidence,),
    )


def _position(
    proposal: CollectiveProposal,
    *,
    stance: CollectivePositionStance = CollectivePositionStance.SUPPORT,
    active: bool = True,
    actor: AgentId = _OWNER,
) -> CollectivePosition:
    return CollectivePosition(
        position_id=("a" if stance is CollectivePositionStance.SUPPORT else "b") * 64,
        actor_id=actor,
        proposal_ref=proposal.proposal_ref,
        revision=proposal.revision,
        stance=stance,
        strength=0.7,
        channel=CollectiveEvidenceChannel.OBSERVED,
        root_ref="root",
        independently_evidenced=True,
        first_tick=2,
        last_tick=2,
        evidence_id="e" * 64,
        active=active,
    )


def test_supported_project_prefers_help_not_execution() -> None:
    proposal = _proposal()
    ledger = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal),),
    )
    assert collective_decision_direction_preference(ledger, tick=5) is (
        ActionDirection.HELP
    )
    assert (
        collective_decision_execution_status(CollectiveTopic.COLLECTIVE_PROJECT, None)
        is CollectiveExecutionStatus.UNKNOWN
    )


def test_withdrawal_and_opposition_remove_the_preference() -> None:
    proposal = _proposal()
    withdrawn = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal, active=False),),
    )
    assert collective_decision_direction_preference(withdrawn, tick=5) is None
    opposed = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal, stance=CollectivePositionStance.OPPOSE),),
    )
    assert collective_decision_direction_preference(opposed, tick=5) is None


def test_expired_or_inactive_proposal_has_no_preference() -> None:
    proposal = _proposal()
    expired = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal),),
    )
    assert collective_decision_direction_preference(expired, tick=30) is None
    retired = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(replace(proposal, status=CollectiveProposalStatus.RETIRED),),
        positions=(_position(proposal),),
    )
    assert collective_decision_direction_preference(retired, tick=5) is None


def test_delegate_stance_and_originator_preference() -> None:
    proposal = _proposal()
    delegated = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal, stance=CollectivePositionStance.DELEGATE),),
    )
    assert collective_decision_direction_preference(delegated, tick=5) is (
        ActionDirection.HELP
    )
    own = _proposal(originator=_OWNER)
    own_ledger = CollectiveDecisionLedger(owner_id=_OWNER, proposals=(own,))
    assert collective_decision_direction_preference(own_ledger, tick=5) is (
        ActionDirection.HELP
    )


def test_topic_directions_and_adapters_are_closed() -> None:
    assert (
        collective_decision_topic_direction(CollectiveTopic.MIGRATION)
        is ActionDirection.MOVE
    )
    assert (
        collective_decision_topic_direction(CollectiveTopic.RESOURCE_ALLOCATION)
        is ActionDirection.FEED
    )
    assert collective_decision_allowed_command(
        CollectiveTopic.COLLECTIVE_PROJECT,
        StartCollectiveProject(project_kind="shared_shelter"),
    )
    assert collective_decision_allowed_command(
        CollectiveTopic.COLLECTIVE_PROJECT,
        ContributeCollectiveProject(project_id=EntityId("site-1")),
    )
    assert collective_decision_allowed_command(
        CollectiveTopic.MIGRATION, Move(destination_id=EntityId("north"))
    )
    assert collective_decision_allowed_command(
        CollectiveTopic.RESOURCE_ALLOCATION,
        Give(recipient_id=EntityId("bob"), item_id=EntityId("berry")),
    )
    assert Talk in COLLECTIVE_TOPIC_COMMANDS[CollectiveTopic.NORM_ENFORCEMENT]
    assert Talk in COLLECTIVE_TOPIC_COMMANDS[CollectiveTopic.SHARED_DEFENSE]
    assert not collective_decision_allowed_command(
        CollectiveTopic.NORM_ENFORCEMENT,
        OpposePublicGood(project_id=EntityId("site-1")),
    )
    assert not collective_decision_allowed_command(
        CollectiveTopic.RESOURCE_ALLOCATION, Wait()
    )
    for topic, commands in COLLECTIVE_TOPIC_COMMANDS.items():
        assert type(topic) is CollectiveTopic
        assert OpposePublicGood not in commands
        assert Store not in commands or topic is CollectiveTopic.STORAGE
        assert commands


def test_influence_classification_distinguishes_stages() -> None:
    kind, reason = classify_collective_decision_influence(
        preferred_direction=ActionDirection.HELP,
        baseline_direction=ActionDirection.WAIT,
        final_direction=ActionDirection.HELP,
    )
    assert kind is CollectiveInfluenceKind.FINAL_COMMAND_CHANGED
    assert reason is None
    kind, reason = classify_collective_decision_influence(
        preferred_direction=ActionDirection.HELP,
        baseline_direction=ActionDirection.WAIT,
        final_direction=ActionDirection.WAIT,
    )
    assert kind is CollectiveInfluenceKind.PREFERENCE_CHANGED
    assert reason is None
    kind, reason = classify_collective_decision_influence(
        preferred_direction=ActionDirection.HELP,
        baseline_direction=ActionDirection.HELP,
        final_direction=ActionDirection.HELP,
    )
    assert kind is CollectiveInfluenceKind.EXECUTED
    kind, reason = classify_collective_decision_influence(
        preferred_direction=None,
        baseline_direction=ActionDirection.WAIT,
        final_direction=ActionDirection.WAIT,
    )
    assert kind is CollectiveInfluenceKind.UNAVAILABLE
    assert reason == "no_comparator"


def test_support_act_does_not_imply_compliance_or_execution() -> None:
    proposal = _proposal()
    ledger = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal),),
    )
    assert ledger.compliance == ()
    assert (
        collective_decision_execution_status(proposal.topic, None)
        is CollectiveExecutionStatus.UNKNOWN
    )
    assert CollectiveComplianceStatus.UNKNOWN.value == "unknown"
    assert CollectiveAct.SUPPORT.value == "support"


def test_non_ledger_inputs_are_ignored() -> None:
    assert collective_decision_direction_preference(None) is None
    assert collective_decision_direction_preference(object()) is None
    with pytest.raises(TypeError):
        collective_decision_topic_direction("migration")  # type: ignore[arg-type]


def test_influence_rows_are_recorded_only_when_candidates_change() -> None:
    from agents.cognition.collective_decision_actions import (
        collective_decision_command_direction,
    )
    from agents.cognition.collective_decisions import (
        CollectiveDecisionBiasAudit,
        append_collective_decision_influence,
    )

    proposal = _proposal()
    ledger = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal),),
    )
    audit = CollectiveDecisionBiasAudit(
        proposal_ref=proposal.proposal_ref,
        revision=0,
        preferred_direction=ActionDirection.HELP,
        baseline_directions=(ActionDirection.WAIT, ActionDirection.HELP),
        biased_directions=(ActionDirection.HELP,),
    )
    changed = append_collective_decision_influence(
        ledger,
        audit=audit,
        final_direction=ActionDirection.HELP,
        tick=5,
    )
    assert len(changed.influence) == 1
    assert changed.influence[0].kind is CollectiveInfluenceKind.PREFERENCE_CHANGED
    overwritten = append_collective_decision_influence(
        ledger,
        audit=audit,
        final_direction=ActionDirection.MOVE,
        tick=5,
    )
    assert (
        overwritten.influence[0].kind is CollectiveInfluenceKind.FINAL_COMMAND_CHANGED
    )
    unchanged_audit = CollectiveDecisionBiasAudit(
        proposal_ref=proposal.proposal_ref,
        revision=0,
        preferred_direction=ActionDirection.HELP,
        baseline_directions=(ActionDirection.HELP,),
        biased_directions=(ActionDirection.HELP,),
    )
    unchanged = append_collective_decision_influence(
        ledger,
        audit=unchanged_audit,
        final_direction=ActionDirection.HELP,
        tick=5,
    )
    assert unchanged.influence == ()
    assert (
        collective_decision_command_direction(
            StartCollectiveProject(project_kind="shared_shelter")
        )
        is ActionDirection.HELP
    )
    assert (
        collective_decision_command_direction(Move(destination_id=EntityId("north")))
        is ActionDirection.MOVE
    )
    assert (
        collective_decision_command_direction(
            Give(recipient_id=EntityId("bob"), item_id=EntityId("berry"))
        )
        is ActionDirection.FEED
    )


def test_late_command_replacement_is_not_credited_as_execution() -> None:
    from agents.cognition.collective_decisions import (
        CollectiveDecisionBiasAudit,
        append_collective_decision_influence,
    )

    proposal = _proposal()
    ledger = CollectiveDecisionLedger(
        owner_id=_OWNER,
        proposals=(proposal,),
        positions=(_position(proposal),),
    )
    audit = CollectiveDecisionBiasAudit(
        proposal_ref=proposal.proposal_ref,
        revision=0,
        preferred_direction=ActionDirection.HELP,
        baseline_directions=(ActionDirection.WAIT, ActionDirection.HELP),
        biased_directions=(ActionDirection.HELP,),
    )
    replaced = append_collective_decision_influence(
        ledger,
        audit=audit,
        final_direction=ActionDirection.COMMUNICATE,
        tick=6,
    )
    assert replaced.influence[0].kind is CollectiveInfluenceKind.FINAL_COMMAND_CHANGED
    assert replaced.influence[0].kind is not CollectiveInfluenceKind.EXECUTED
