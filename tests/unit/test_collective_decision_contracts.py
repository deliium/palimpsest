"""Owner-scoped collective-decision contracts, identity, and policy."""

from __future__ import annotations

import math

import pytest

from agents.cognition.collective_decisions import (
    COLLECTIVE_DECISION_POLICY_VERSION,
    FORBIDDEN_COLLECTIVE_DECISION_FIELD_NAMES,
    CollectiveAct,
    CollectiveCompliance,
    CollectiveComplianceStatus,
    CollectiveDecisionLedger,
    CollectiveDecisionPolicy,
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
    CollectiveRetraction,
    CollectiveTopic,
    collective_context_key,
    collective_decision_evidence_id,
    collective_proposal_id,
    collective_proposal_ref,
    default_collective_decision_policy,
    empty_collective_decision_ledger,
    require_owner_collective_decisions,
)
from agents.models import AgentId

_OWNER = AgentId("alice")
_OTHER = AgentId("bob")
_CONTEXT = "a" * 16
_TICK = 3


def _ref(topic: CollectiveTopic = CollectiveTopic.COLLECTIVE_PROJECT) -> str:
    return collective_proposal_ref(
        _OWNER,
        originator_id=_OWNER,
        topic=topic,
        context_key=_CONTEXT,
        inception_tick=_TICK,
        inception_lineage="first-opportunity",
    )


def _evidence(proposal_ref: str, *, ordinal: int = 0) -> CollectiveEvidence:
    channel = CollectiveEvidenceChannel.OBSERVED
    return CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            proposal_ref, ordinal, channel, f"lineage-{ordinal}"
        ),
        ordinal=ordinal,
        channel=channel,
        lineage_ref=f"lineage-{ordinal}",
        root_ref=f"root-{ordinal}",
        tick=_TICK + ordinal,
    )


def _proposal(
    *,
    owner: AgentId = _OWNER,
    topic: CollectiveTopic = CollectiveTopic.COLLECTIVE_PROJECT,
    revision: int = 0,
    evidence: tuple[CollectiveEvidence, ...] | None = None,
    terms: tuple[str, ...] = ("start_project",),
    status: CollectiveProposalStatus = CollectiveProposalStatus.ACTIVE,
) -> CollectiveProposal:
    ref = _ref(topic)
    return CollectiveProposal(
        proposal_id=collective_proposal_id(_OWNER, ref, revision),
        owner_id=owner,
        proposal_ref=ref,
        revision=revision,
        topic=topic,
        context_key=_CONTEXT,
        action_token="start_project",
        first_tick=_TICK,
        last_tick=_TICK,
        window_first_tick=_TICK,
        window_last_tick=_TICK + 8,
        status=status,
        originator_id=_OWNER,
        target_token="field",
        terms=terms,
        evidence=(_evidence(ref),) if evidence is None else evidence,
    )


def test_policy_locks_constants() -> None:
    policy = default_collective_decision_policy()
    assert policy.version == COLLECTIVE_DECISION_POLICY_VERSION
    assert COLLECTIVE_DECISION_POLICY_VERSION == "collective-decisions.v1"
    assert policy.default_proposal_window == 8
    assert policy.max_proposal_window == 32
    assert policy.evidence_retention == 64
    assert policy.reference_freshness == 32
    assert policy.max_proposals == 16
    assert policy.max_positions == 32
    with pytest.raises(ValueError):
        CollectiveDecisionPolicy(default_proposal_window=9)
    with pytest.raises(ValueError):
        CollectiveDecisionPolicy(version="other")


def test_all_six_acts_and_topics_are_closed() -> None:
    assert {act.value for act in CollectiveAct} == {
        "propose",
        "support",
        "oppose",
        "delegate",
        "withdraw_support",
        "coordinate",
    }
    assert {topic.value for topic in CollectiveTopic} == {
        "collective_project",
        "resource_allocation",
        "migration",
        "shared_defense",
        "storage",
        "norm_enforcement",
    }
    for topic in CollectiveTopic:
        proposal = _proposal(topic=topic)
        assert proposal.topic is topic
        assert proposal.supports_tick(_TICK)


def test_proposal_identity_is_stable_and_owner_scoped() -> None:
    proposal = _proposal()
    assert proposal.proposal_id == collective_proposal_id(
        _OWNER, proposal.proposal_ref, proposal.revision
    )
    assert proposal.proposal_id != collective_proposal_id(
        _OTHER, proposal.proposal_ref, proposal.revision
    )
    assert proposal.proposal_id != collective_proposal_id(
        _OWNER, proposal.proposal_ref, proposal.revision + 1
    )
    with pytest.raises(ValueError):
        CollectiveProposal(
            proposal_id="f" * 64,
            owner_id=_OWNER,
            proposal_ref=proposal.proposal_ref,
            revision=proposal.revision,
            topic=proposal.topic,
            context_key=_CONTEXT,
            action_token="start_project",
            first_tick=_TICK,
            last_tick=_TICK,
            window_first_tick=_TICK,
            window_last_tick=_TICK + 8,
        )


def test_proposal_rejects_malformed_terms_and_windows() -> None:
    ref = _ref()
    with pytest.raises(ValueError):
        _proposal(terms=("bad term",))
    with pytest.raises(ValueError):
        _proposal(terms=("a", "a"))
    with pytest.raises(ValueError):
        CollectiveProposal(
            proposal_id=collective_proposal_id(_OWNER, ref, 0),
            owner_id=_OWNER,
            proposal_ref=ref,
            revision=0,
            topic=CollectiveTopic.MIGRATION,
            context_key=_CONTEXT,
            action_token="move",
            first_tick=5,
            last_tick=4,
            window_first_tick=5,
            window_last_tick=6,
            evidence=(_evidence(ref),),
        )


def test_evidence_is_monotonic_and_bounded() -> None:
    ref = _ref()
    first = _evidence(ref, ordinal=1)
    zero = _evidence(ref, ordinal=0)
    with pytest.raises(ValueError):
        _proposal(evidence=(first, zero))
    duplicate = (zero, zero)
    with pytest.raises(ValueError):
        _proposal(evidence=duplicate)
    too_many = tuple(_evidence(ref, ordinal=index) for index in range(33))
    with pytest.raises(ValueError):
        _proposal(evidence=too_many)


def test_ledger_owner_and_caps() -> None:
    proposal = _proposal()
    ledger = CollectiveDecisionLedger(owner_id=_OWNER, proposals=(proposal,))
    assert ledger.enabled
    assert ledger.has_content
    assert ledger.coverage == "complete"
    assert ledger.actionable_proposals == (proposal,)
    foreign = CollectiveProposal(
        proposal_id=collective_proposal_id(_OTHER, proposal.proposal_ref, 0),
        owner_id=_OTHER,
        proposal_ref=proposal.proposal_ref,
        revision=0,
        topic=proposal.topic,
        context_key=_CONTEXT,
        action_token="start_project",
        first_tick=_TICK,
        last_tick=_TICK,
        window_first_tick=_TICK,
        window_last_tick=_TICK + 8,
        evidence=(_evidence(proposal.proposal_ref),),
    )
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(owner_id=_OWNER, proposals=(foreign,))
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(
            owner_id=_OWNER,
            proposals=tuple(_proposal(revision=index) for index in range(17)),
        )
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(owner_id="alice")  # type: ignore[arg-type]


def test_empty_ledger_and_foreign_carry() -> None:
    ledger = empty_collective_decision_ledger(_OWNER)
    assert not ledger.has_content
    assert ledger.coverage == "complete"
    assert ledger.first_observed_tick is None
    require_owner_collective_decisions(None, _OWNER, field_name="carry")
    require_owner_collective_decisions(ledger, _OWNER, field_name="carry")
    with pytest.raises(ValueError):
        require_owner_collective_decisions(ledger, _OTHER, field_name="carry")
    with pytest.raises(TypeError):
        require_owner_collective_decisions(object(), _OWNER, field_name="carry")


def test_ledger_window_and_pruning_coverage() -> None:
    ledger = CollectiveDecisionLedger(
        owner_id=_OWNER,
        first_observed_tick=2,
        last_observed_tick=7,
        observation_count=6,
        pruned_evidence_count=1,
    )
    assert ledger.coverage == "partial"
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(owner_id=_OWNER, first_observed_tick=2)
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(
            owner_id=_OWNER,
            first_observed_tick=5,
            last_observed_tick=3,
            observation_count=1,
        )
    with pytest.raises(ValueError):
        CollectiveDecisionLedger(owner_id=_OWNER, observation_count=1)


def test_position_delegation_and_retraction_contracts() -> None:
    ref = _ref()
    position = CollectivePosition(
        position_id="a" * 64,
        actor_id=_OWNER,
        proposal_ref=ref,
        revision=0,
        stance=CollectivePositionStance.SUPPORT,
        strength=0.7,
        channel=CollectiveEvidenceChannel.OBSERVED,
        root_ref="root",
        independently_evidenced=True,
        first_tick=1,
        last_tick=2,
        evidence_id="b" * 64,
    )
    assert position.active
    with pytest.raises(ValueError):
        CollectivePosition(
            position_id="a" * 64,
            actor_id=_OWNER,
            proposal_ref=ref,
            revision=0,
            stance=CollectivePositionStance.SUPPORT,
            strength=math.nan,
            channel=CollectiveEvidenceChannel.OBSERVED,
            root_ref="root",
            independently_evidenced=True,
            first_tick=1,
            last_tick=2,
            evidence_id="b" * 64,
        )
    delegation = CollectiveDelegation(
        delegation_id="c" * 64,
        delegator_id=_OWNER,
        delegate_id=_OTHER,
        proposal_ref=ref,
        revision=0,
        strength=0.5,
        first_tick=1,
        last_tick=1,
        expires_tick=5,
        evidence_id="d" * 64,
    )
    assert delegation.active
    with pytest.raises(ValueError):
        CollectiveDelegation(
            delegation_id="c" * 64,
            delegator_id=_OWNER,
            delegate_id=_OWNER,
            proposal_ref=ref,
            revision=0,
            strength=0.5,
            first_tick=1,
            last_tick=1,
            expires_tick=5,
            evidence_id="d" * 64,
        )
    retraction = CollectiveRetraction(
        retraction_id="e" * 64,
        actor_id=_OWNER,
        target_kind="position",
        target_id=position.position_id,
        proposal_ref=ref,
        revision=0,
        tick=3,
        evidence_id="f" * 64,
    )
    assert retraction.target_kind == "position"
    with pytest.raises(ValueError):
        CollectiveRetraction(
            retraction_id="e" * 64,
            actor_id=_OWNER,
            target_kind="vote",
            target_id=position.position_id,
            proposal_ref=ref,
            revision=0,
            tick=3,
            evidence_id="f" * 64,
        )


def test_outcome_compliance_and_influence_contracts() -> None:
    ref = _ref()
    outcome = CollectiveOutcome(
        outcome_id="a" * 64,
        proposal_ref=ref,
        revision=0,
        kind=CollectiveOutcomeKind.CLAIMED,
        execution_status=CollectiveExecutionStatus.UNKNOWN,
        claimed=True,
        first_tick=1,
        last_tick=2,
    )
    assert outcome.claimed
    compliance = CollectiveCompliance(
        compliance_id="b" * 64,
        actor_id=_OWNER,
        proposal_ref=ref,
        revision=0,
        status=CollectiveComplianceStatus.MATCHED,
        window_first_tick=1,
        window_last_tick=4,
    )
    assert compliance.status is CollectiveComplianceStatus.MATCHED
    influence = CollectiveInfluence(
        influence_id="c" * 64,
        proposal_ref=ref,
        revision=0,
        source_act=CollectiveAct.SUPPORT,
        kind=CollectiveInfluenceKind.FINAL_COMMAND_CHANGED,
        strength=0.4,
        tick=2,
    )
    assert influence.kind is CollectiveInfluenceKind.FINAL_COMMAND_CHANGED
    unavailable = CollectiveInfluence(
        influence_id="d" * 64,
        proposal_ref=ref,
        revision=0,
        source_act=CollectiveAct.COORDINATE,
        kind=CollectiveInfluenceKind.UNAVAILABLE,
        strength=0.0,
        tick=2,
        unavailable_reason="no_comparator",
    )
    assert unavailable.unavailable_reason == "no_comparator"
    with pytest.raises(ValueError):
        CollectiveInfluence(
            influence_id="d" * 64,
            proposal_ref=ref,
            revision=0,
            source_act=CollectiveAct.COORDINATE,
            kind=CollectiveInfluenceKind.UNAVAILABLE,
            strength=0.0,
            tick=2,
        )


def test_reprs_are_metadata_only() -> None:
    proposal = _proposal(terms=("secret_term",))
    for value in (
        proposal,
        proposal.evidence[0],
        _proposal().supports_tick(_TICK),
        empty_collective_decision_ledger(_OWNER),
    ):
        rendered = repr(value)
        assert "secret_term" not in rendered
        assert "field" not in rendered


def test_forbidden_political_field_names_are_locked() -> None:
    for name in (
        "vote",
        "majority",
        "quorum",
        "election",
        "legitimacy",
        "government",
        "current_decision",
    ):
        assert name in FORBIDDEN_COLLECTIVE_DECISION_FIELD_NAMES


def test_context_key_requires_observation() -> None:
    with pytest.raises(TypeError):
        collective_context_key(object())  # type: ignore[arg-type]
