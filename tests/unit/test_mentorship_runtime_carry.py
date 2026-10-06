"""Unit tests for mentorship ledger runtime / checkpoint carry."""

from __future__ import annotations

import logging

from agents.cognition.mentorship import (
    MentorshipBondRole,
    MentorshipContentKindId,
    empty_mentorship_ledger,
    form_or_reinforce_mentorship_bond,
)
from agents.cognition.models import SubjectiveSnapshot
from agents.models import AgentId
from memory.models import MemoryTrace

_LOG = logging.getLogger("tests.mentorship_runtime_carry")


def test_subjective_snapshot_carries_mentorship() -> None:
    _LOG.debug("case_id=subjective_snapshot_mentorship")
    owner = AgentId("bob")
    ledger = form_or_reinforce_mentorship_bond(
        empty_mentorship_ledger(owner),
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        tick=1,
        successful_act_count=2,
        projected_trust=0.5,
        form_after_successful_acts=1,
        min_trust=0.0,
        reinforce_on_learning_evidence=False,
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        mentorship=ledger,
    )
    assert snapshot.mentorship is ledger
    assert len(snapshot.mentorship.bonds) == 1


def test_empty_mentorship_blank_slate_compatible() -> None:
    _LOG.debug("case_id=empty_mentorship_blank_slate")
    owner = AgentId("entrant")
    ledger = empty_mentorship_ledger(owner)
    assert isinstance(ledger.bonds, tuple)
    assert ledger.bonds == ()
    assert ledger.lineage == ()
    # MemoryTrace type import keeps snapshot contract surface loaded.
    assert MemoryTrace is not None
