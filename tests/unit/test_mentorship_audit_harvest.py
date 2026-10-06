"""MentorshipAudit harvest on SimulationRunnerResult."""

from __future__ import annotations

from agents.cognition.mentorship import (
    MentorshipAudit,
    MentorshipBondRole,
    MentorshipContentKindId,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
)


def test_result_accepts_metadata_only_mentorship_audits() -> None:
    audit = MentorshipAudit(
        owner_id=AgentId("bob"),
        partner_agent_id=AgentId("alice"),
        role=MentorshipBondRole.APPRENTICE,
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        hop_index=0,
        attempt_count=1,
        learning_evidence_count=1,
        confidence_band="mid",
        mutated=False,
        tick=3,
        reason_code="teaching_uptake",
    )
    result = SimulationRunnerResult(
        run_id=RunId("run-mentorship-audit"),
        ticks_committed=3,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cognition_counters=CognitionCounters(),
        mentorship_audits=(audit,),
    )
    assert len(result.mentorship_audits) == 1
    row = result.mentorship_audits[0]
    assert type(row) is MentorshipAudit
    assert not hasattr(row, "content_fingerprint")
    assert not hasattr(row, "content_key")
