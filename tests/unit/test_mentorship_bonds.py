"""Unit tests for mentorship bond form / reinforce / decay / caps."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.mentorship import (
    MentorshipBondRole,
    MentorshipContentKindId,
    decay_mentorship_bonds,
    empty_mentorship_ledger,
    form_or_reinforce_mentorship_bond,
)
from agents.models import AgentId

_LOG = logging.getLogger("tests.mentorship_bonds")


def test_bond_forms_after_acts_and_trust(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=bond_forms_after_acts_and_trust")
    owner = AgentId("bob")
    ledger = empty_mentorship_ledger(owner, max_bonds=2)
    skipped = form_or_reinforce_mentorship_bond(
        ledger,
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        tick=1,
        successful_act_count=1,
        projected_trust=0.5,
        form_after_successful_acts=2,
        min_trust=0.2,
        reinforce_on_learning_evidence=True,
    )
    assert skipped.bonds == ()
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        formed = form_or_reinforce_mentorship_bond(
            skipped,
            partner_agent_id=AgentId("alice"),
            owner_role=MentorshipBondRole.APPRENTICE,
            content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
            tick=2,
            successful_act_count=2,
            projected_trust=0.5,
            form_after_successful_acts=2,
            min_trust=0.2,
            reinforce_on_learning_evidence=True,
        )
    assert len(formed.bonds) == 1
    assert formed.bonds[0].role is MentorshipBondRole.APPRENTICE
    assert "bond_formed" in caplog.text


def test_bond_reinforce_and_decay() -> None:
    _LOG.debug("case_id=bond_reinforce_and_decay")
    owner = AgentId("bob")
    ledger = empty_mentorship_ledger(owner)
    formed = form_or_reinforce_mentorship_bond(
        ledger,
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.WARNINGS,),
        tick=1,
        successful_act_count=3,
        projected_trust=0.8,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
        initial_strength=0.4,
    )
    reinforced = form_or_reinforce_mentorship_bond(
        formed,
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.WARNINGS,),
        tick=2,
        successful_act_count=4,
        projected_trust=0.8,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
        learning_evidence=True,
        reinforce_delta=0.1,
    )
    assert reinforced.bonds[0].strength > formed.bonds[0].strength
    decayed = decay_mentorship_bonds(
        reinforced, tick=5, decay_per_tick=0.2, idle_ticks_before_decay=1
    )
    assert decayed.bonds[0].strength < reinforced.bonds[0].strength


def test_max_bonds_eviction() -> None:
    _LOG.debug("case_id=max_bonds_eviction")
    owner = AgentId("bob")
    ledger = empty_mentorship_ledger(owner, max_bonds=2)
    current = ledger
    for index, partner in enumerate(("alice", "carol", "dave"), start=1):
        current = form_or_reinforce_mentorship_bond(
            current,
            partner_agent_id=AgentId(partner),
            owner_role=MentorshipBondRole.APPRENTICE,
            content_kinds=(MentorshipContentKindId.STORIES,),
            tick=index,
            successful_act_count=2,
            projected_trust=0.9,
            form_after_successful_acts=1,
            min_trust=0.0,
            reinforce_on_learning_evidence=False,
            initial_strength=0.1 * index,
        )
    assert len(current.bonds) == 2
    partners = {bond.partner_agent_id.value for bond in current.bonds}
    assert "alice" not in partners
