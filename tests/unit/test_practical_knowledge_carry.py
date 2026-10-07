"""Unit tests for practical-knowledge ledger runtime / checkpoint carry."""

from __future__ import annotations

import logging

from agents.cognition.configuration import CognitionLoopConfig, build_cognitive_loop
from agents.cognition.models import CognitiveLoopInput, InternalAgentState, SubjectiveSnapshot
from agents.cognition.practical_knowledge import (
    KnowledgeTransmissionOrigin,
    PracticalKnowledgeAudit,
    PracticalKnowledgeKind,
    empty_practical_knowledge_ledger,
    entry_to_audit,
    form_or_reinforce_practical_knowledge,
    practical_knowledge_content_key,
)
from agents.models import AgentId
from memory.models import MemoryTrace
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.runner_models import example_knowledge_genealogy_spec
from tests.unit.test_identity_runtime import _observation, _runtime

_LOG = logging.getLogger("tests.practical_knowledge_carry")
_KINDS = ("foraging_method",)


def _filled_ledger(owner: AgentId):
    return form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(owner),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("berry-pick"),
        content_fingerprint=("cue-a", "cue-b"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=_KINDS,
        evidence_refs=("practice:1",),
    )


def test_subjective_snapshot_carries_practical_knowledge() -> None:
    _LOG.debug("case_id=subjective_snapshot_practical_knowledge")
    owner = AgentId("bob")
    ledger = _filled_ledger(owner)
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        practical_knowledge=ledger,
    )
    assert snapshot.practical_knowledge is ledger
    assert len(snapshot.practical_knowledge.entries) == 1


def test_empty_practical_knowledge_blank_slate_compatible() -> None:
    _LOG.debug("case_id=empty_practical_knowledge_blank_slate")
    owner = AgentId("entrant")
    ledger = empty_practical_knowledge_ledger(owner)
    assert isinstance(ledger.entries, tuple)
    assert ledger.entries == ()
    assert MemoryTrace is not None


def test_prepare_channel_off_returns_none() -> None:
    _LOG.debug("case_id=prepare_channel_off")
    owner = AgentId("agent-1")
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            practical_knowledge=_filled_ledger(owner),
        ),
    )
    prepared = loop._prepare_practical_knowledge(loop_input)
    assert prepared is None
    assert loop._last_practical_knowledge_audits == ()


def test_prepare_channel_on_empty_synthesize() -> None:
    _LOG.debug("case_id=prepare_empty_synthesize")
    owner = AgentId("agent-1")
    spec = example_knowledge_genealogy_spec()
    loop = build_cognitive_loop(
        CognitionLoopConfig(),
        knowledge_genealogy_spec=spec,
        knowledge_genealogy_seed_material="seed-carry",
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
        ),
    )
    prepared = loop._prepare_practical_knowledge(loop_input)
    assert prepared is not None
    assert prepared.owner_id == owner
    assert prepared.entries == ()
    assert prepared.max_entries == spec.lineage_policy.max_entries_per_owner


def test_prepare_channel_on_carries_existing_ledger() -> None:
    _LOG.debug("case_id=prepare_carry")
    owner = AgentId("agent-1")
    ledger = _filled_ledger(owner)
    loop = build_cognitive_loop(
        CognitionLoopConfig(),
        knowledge_genealogy_spec=example_knowledge_genealogy_spec(),
        knowledge_genealogy_seed_material="seed-carry",
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            practical_knowledge=ledger,
        ),
    )
    prepared = loop._prepare_practical_knowledge(loop_input)
    assert prepared is ledger


def test_commit_channel_off_clears_store() -> None:
    _LOG.debug("case_id=commit_channel_off")
    runtime, _reader = _runtime()
    owner = runtime.agent_id
    runtime._practical_knowledge = _filled_ledger(owner)
    runtime._commit_practical_knowledge(runtime._practical_knowledge, tick=2)
    assert runtime._practical_knowledge is None
    assert runtime.export_practical_knowledge_audits() == ()


def test_checkpoint_copies_practical_knowledge() -> None:
    _LOG.debug("case_id=checkpoint_carry_restore")
    runtime, _reader = _runtime()
    ledger = _filled_ledger(runtime.agent_id)
    runtime._practical_knowledge = ledger
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    assert exported.practical_knowledge is ledger
    fresh, _ = _runtime()
    fresh.restore_runtime_checkpoint(exported)
    assert fresh._practical_knowledge is ledger
    blank = AgentRuntimeCheckpoint(
        agent_id=runtime.agent_id,
        status=exported.status,
        internal_state=exported.internal_state,
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=runtime.agent.goals,
    )
    assert blank.practical_knowledge is None
    runtime.restore_runtime_checkpoint(blank)
    assert runtime._practical_knowledge is None


def test_audit_duck_typing_stable() -> None:
    _LOG.debug("case_id=audit_duck_typing")
    owner = AgentId("bob")
    ledger = _filled_ledger(owner)
    audit = entry_to_audit(ledger.entries[0], tick=3, reason_code="formed")
    assert type(audit) is PracticalKnowledgeAudit
    assert audit.owner_id == owner
    assert audit.kind == "foraging_method"
    assert audit.origin == "independent_discovery"
    assert audit.hop_index == 0
    assert "content_fingerprint" not in audit.__dataclass_fields__
