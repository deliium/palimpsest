"""Hidden communication-intent audits stay off agent-facing channels."""

from __future__ import annotations

import inspect
import logging
from dataclasses import fields
from types import SimpleNamespace

import pytest

from agents.cognition.communication_strategy import (
    CommunicationDivergence,
    CommunicationFactor,
    CommunicationIntentAudit,
    CommunicationStrategy,
    SpeakerStance,
    communication_intent,
)
from agents.models import AgentId
from memory.belief_formation import evaluate_communicated_testimony
from memory.models import MemoryTrace
from simulation.runner_models import SimulationRunnerResultDocument
from simulation.subjective_serialization import SUBJECTIVE_SCHEMA_VERSION
from social.models import CommunicationEnvelope
from world.communications import (
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.observations import ObservedCommunication

_FORBIDDEN = {
    "strategy",
    "stance",
    "memory_error",
    "uncertain_inference",
    "deliberate_deception",
}


def test_receiver_records_do_not_carry_strategy_labels() -> None:
    for model in (
        StructuredUtterance,
        DeclaredTransmission,
        ObservedCommunication,
        CommunicationEnvelope,
        MemoryTrace,
    ):
        names = {item.name for item in fields(model)}
        assert names.isdisjoint(_FORBIDDEN)
    parameters = inspect.signature(evaluate_communicated_testimony).parameters
    assert "strategy" not in parameters
    assert "category" not in parameters


def test_result_document_and_subjective_schema_omit_the_audit() -> None:
    document_names = {item.name for item in fields(SimulationRunnerResultDocument)}
    assert "communication_intent_audits" not in document_names
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"


def test_trace_projection_does_not_name_strategy_fields() -> None:
    from pathlib import Path

    source = Path("src/agents/cognition/trace.py").read_text(encoding="utf-8")
    assert "communication_intent" not in source
    assert "deliberate_deception" not in source


@pytest.mark.asyncio
async def test_disabled_finalize_and_abort_append_no_audit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_agent_runtime import _runtime, _self, _token

    runtime, _memories, _beliefs = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)
    assert runtime.export_communication_intent_audits() == ()

    prepared_again = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    finalized = await runtime.bind_effective_command(prepared_again)
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        await runtime.finalize_pending(finalized)
    assert runtime.export_communication_intent_audits() == ()
    skipped = [
        record.getMessage()
        for record in caplog.records
        if "communication_intent_audit_skipped" in record.getMessage()
    ]
    assert skipped
    assert "audit_present=False" in skipped[-1]


def test_commit_keeps_strategy_and_stance_out_of_atom_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_agent_runtime import _runtime

    owner = AgentId("agent-1")
    intent = communication_intent(
        owner_id=owner,
        recipient_id=AgentId("agent-2"),
        tick=4,
        strategy=CommunicationStrategy.TRUTHFUL,
        stance=SpeakerStance.ASSERT_MATCH,
        divergence=CommunicationDivergence.NONE,
        source_basis=CommunicationSourceBasis.BELIEF,
        source_confidence=0.8,
        source_atom_tokens=("food",),
        cited_event_id=None,
        factor_codes=(CommunicationFactor.NORMS_UNAVAILABLE,),
        delivered=True,
    )
    audit = CommunicationIntentAudit(
        intent_id=intent.intent_id,
        owner_id=intent.owner_id,
        recipient_id=intent.recipient_id,
        tick=intent.tick,
        strategy=intent.strategy,
        stance=intent.stance,
        divergence=intent.divergence,
        source_basis=intent.source_basis,
        source_confidence=intent.source_confidence,
        source_atom_tokens=intent.source_atom_tokens,
        cited_event_id=intent.cited_event_id,
        factor_codes=intent.factor_codes,
        delivered=intent.delivered,
        fallback_used=False,
    )
    runtime, _memories, _beliefs = _runtime()
    with caplog.at_level(logging.DEBUG, logger="simulation.agent_runtime"):
        runtime._commit_communication_intent(
            SimpleNamespace(
                communication_intent=intent,
                communication_intent_audit=audit,
            ),
            4,
        )
    exported = runtime.export_communication_intent_audits()
    assert exported == (audit,)
    message = next(
        record.getMessage()
        for record in caplog.records
        if "communication_intent_audit_committed" in record.getMessage()
    )
    assert "strategy=truthful" in message
    assert "stance=assert_match" in message
    assert "food" not in message
