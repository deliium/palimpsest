"""CulturalFeatureAudit harvest on SimulationRunnerResult."""

from __future__ import annotations

from agents.cognition.cultural_features import (
    CulturalFeatureAudit,
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
)


def test_result_accepts_metadata_only_cultural_feature_audits() -> None:
    audit = CulturalFeatureAudit(
        owner_id=AgentId("bob"),
        feature_kind=CulturalFeatureKindId.TERM,
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        hop_index=0,
        mutated=False,
        recombined=False,
        parent_count=0,
        confidence_band="mid",
        digest_id_token="dig-1",
        tick=2,
        reason_code="channel_formed",
    )
    result = SimulationRunnerResult(
        run_id=RunId("run-cultural-audit"),
        ticks_committed=2,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cognition_counters=CognitionCounters(),
        cultural_feature_audits=(audit,),
    )
    assert len(result.cultural_feature_audits) == 1
    row = result.cultural_feature_audits[0]
    assert type(row) is CulturalFeatureAudit
    assert not hasattr(row, "content_fingerprint")
    assert not hasattr(row, "content_key")
