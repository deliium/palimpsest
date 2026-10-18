"""V2 narrative ledgers survive runtime checkpoints, restore, and export."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordRef,
    NarrativeRecordRole,
    NarrativeSourceLoss,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeTheme,
    NarrativeThemeBasis,
    NarrativeTransition,
    NarrativeTransitionKind,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    narrative_content_fingerprint,
    narrative_transition_id,
    narrative_variant_id,
)
from agents.cognition.defaults import default_cognitive_loop
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import RunnerStopReasonCode, SimulationRunnerResult
from tests.unit.test_cultural_narratives_runtime import _runtime

_OWNER = AgentId("agent-1")


def _v2_ledger(owner: AgentId = _OWNER) -> NarrativeLedger:
    content = NarrativeContent(concepts=("founding",), text="tell_story")
    variant_id = narrative_variant_id(
        owner, narrative_content_fingerprint(content), 0, ""
    )
    witness = NarrativeWitness(
        witness_agent_id=owner,
        kind=NarrativeWitnessKind.FIRST_HAND,
        hop_index=0,
        first_seen_tick=1,
        last_seen_tick=1,
    )
    record = NarrativeRecordRef(
        record_id="record-1",
        role=NarrativeRecordRole.READ,
        observed_revision=1,
        tick=1,
        integrity="intact",
    )
    transition = NarrativeTransition(
        transition_id=narrative_transition_id(
            owner, variant_id, NarrativeTransitionKind.MINTED, 1, "origin"
        ),
        kind=NarrativeTransitionKind.MINTED,
        tick=1,
        carrier_agent_id=owner,
    )
    variant = NarrativeVariant(
        variant_id=variant_id,
        owner_id=owner,
        content=content,
        content_fingerprint=narrative_content_fingerprint(content),
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.5,
        first_tick=1,
        last_tick=1,
        source_event_id="event-1",
        carrier_agent_ids=(owner.value,),
        source_witnesses=(witness,),
        first_hand=True,
        record_refs=(record,),
        transitions=(transition,),
        source_loss=NarrativeSourceLoss(
            state=NarrativeSourceLossState.INTACT,
            reason=NarrativeSourceLossReason.NONE,
            tick=1,
            known_witness_count=1,
            dead_witness_count=0,
            record_backed=True,
        ),
        themes=(NarrativeTheme.FOUNDERS,),
        theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    )
    return NarrativeLedger(
        owner_id=owner,
        variants=(variant,),
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    )


def test_runtime_restore_and_export_preserve_v2_provenance() -> None:
    runtime = _runtime(default_cognitive_loop())
    ledger = _v2_ledger()
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.cultural_narratives is None
    from dataclasses import replace

    restored = replace(checkpoint, cultural_narratives=ledger)
    runtime.restore_runtime_checkpoint(restored)
    exported = runtime.export_cultural_narratives()
    assert exported is ledger
    assert exported.variants[0].source_witnesses[0].kind is (
        NarrativeWitnessKind.FIRST_HAND
    )
    assert exported.variants[0].record_refs[0].record_id == "record-1"
    assert exported.variants[0].transitions[0].kind is (
        NarrativeTransitionKind.MINTED
    )
    assert exported.variants[0].themes == (NarrativeTheme.FOUNDERS,)
    assert exported.variants[0].source_loss is not None


def test_runner_result_carries_owner_ordered_ledgers() -> None:
    ledger = _v2_ledger()
    result = SimulationRunnerResult(
        run_id=RunId("run-1"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cultural_narrative_ledgers=(ledger,),
    )
    assert result.cultural_narrative_ledgers == (ledger,)
    assert result.terminology_ledgers == ()
    with __import__("pytest").raises(TypeError):
        SimulationRunnerResult(
            run_id=RunId("run-2"),
            ticks_committed=1,
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            attempt_receipts=(),
            cultural_narrative_ledgers=(None,),
        )
