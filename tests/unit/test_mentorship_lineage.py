"""Unit tests for taught-content lineage hops and mutation."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.mentorship import (
    LINEAGE_FIRST_HOP_INDEX,
    MentorshipContentKindId,
    empty_mentorship_ledger,
    mutate_taught_content_lineage,
    record_taught_content_lineage,
)
from agents.models import AgentId

_LOG = logging.getLogger("tests.mentorship_lineage")


def test_first_hop_index_zero_and_chain() -> None:
    _LOG.debug("case_id=first_hop_and_chain")
    bob = AgentId("bob")
    ledger = empty_mentorship_ledger(bob)
    hop0 = record_taught_content_lineage(
        ledger,
        teacher_agent_id=AgentId("alice"),
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        content_key="skill:forge",
        content_fingerprint="fp:bob:v1",
        tick=1,
        evidence_refs=("comm:1",),
        confidence=0.4,
        uptake_succeeded=True,
        record_attempts=True,
        max_hop_depth=4,
    )
    assert hop0.lineage[0].hop_index == LINEAGE_FIRST_HOP_INDEX
    assert hop0.lineage[0].lineage_id is not None

    carol = AgentId("carol")
    carol_ledger = empty_mentorship_ledger(carol)
    # Carol learns from Bob's mutated teaching; parent hop provided explicitly.
    hop1 = record_taught_content_lineage(
        carol_ledger,
        teacher_agent_id=bob,
        content_kind=MentorshipContentKindId.PRACTICAL_SKILLS,
        content_key="skill:forge",
        content_fingerprint="fp:carol:v1",
        tick=2,
        evidence_refs=("comm:2",),
        confidence=0.35,
        uptake_succeeded=True,
        record_attempts=True,
        max_hop_depth=4,
        parent_lineage_id=hop0.lineage[0].lineage_id,
        lineage_root_id=hop0.lineage[0].lineage_root_id,
        parent_hop_index=hop0.lineage[0].hop_index,
    )
    assert hop1.lineage[0].hop_index == 1
    assert hop1.lineage[0].lineage_root_id == hop0.lineage[0].lineage_root_id


def test_hop_cap_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=hop_cap_rejected")
    owner = AgentId("dave")
    ledger = empty_mentorship_ledger(owner)
    with caplog.at_level(logging.ERROR, logger="agents.cognition.mentorship"):
        with pytest.raises(ValueError, match="mentorship_hop_cap"):
            record_taught_content_lineage(
                ledger,
                teacher_agent_id=AgentId("carol"),
                content_kind=MentorshipContentKindId.STORIES,
                content_key="story:flood",
                content_fingerprint="fp:dave:v1",
                tick=3,
                evidence_refs=("comm:3",),
                confidence=0.2,
                uptake_succeeded=True,
                record_attempts=True,
                max_hop_depth=2,
                parent_lineage_id="lin:parent",
                lineage_root_id="root:alice:stories:story:flood",
                parent_hop_index=1,
            )
    assert "mentorship_hop_cap" in caplog.text


def test_learner_mutation_sets_flag() -> None:
    _LOG.debug("case_id=learner_mutation")
    owner = AgentId("bob")
    ledger = record_taught_content_lineage(
        empty_mentorship_ledger(owner),
        teacher_agent_id=AgentId("alice"),
        content_kind=MentorshipContentKindId.FACTUAL_BELIEFS,
        content_key="belief:water",
        content_fingerprint="fp:bob:v1",
        tick=1,
        evidence_refs=("evt:1",),
        confidence=0.5,
        uptake_succeeded=True,
        record_attempts=True,
        max_hop_depth=4,
    )
    lineage_id = ledger.lineage[0].lineage_id
    assert lineage_id is not None
    mutated = mutate_taught_content_lineage(
        ledger,
        lineage_id=lineage_id,
        content_fingerprint="fp:bob:v2",
        confidence=0.7,
        tick=4,
        allow_learner_mutation=True,
        mutation_requires_evidence=True,
        owner_evidence_present=True,
    )
    assert mutated.lineage[0].mutated is True
    assert mutated.lineage[0].content_fingerprint == "fp:bob:v2"


def test_missing_teacher_provenance_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=missing_teacher")
    with caplog.at_level(logging.ERROR, logger="agents.cognition.mentorship"):
        with pytest.raises(ValueError, match="provenance_required"):
            record_taught_content_lineage(
                empty_mentorship_ledger(AgentId("bob")),
                teacher_agent_id="alice",  # type: ignore[arg-type]
                content_kind=MentorshipContentKindId.WARNINGS,
                content_key="warn:cliff",
                content_fingerprint="fp:bob:warn",
                tick=1,
                evidence_refs=("evt:1",),
                confidence=0.3,
                uptake_succeeded=True,
                record_attempts=True,
                max_hop_depth=4,
            )
    assert "provenance_required" in caplog.text
