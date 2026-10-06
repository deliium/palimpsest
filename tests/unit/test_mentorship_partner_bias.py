"""Partner bias float term for bonded communicate futures."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.mentorship import (
    MentorshipBondRole,
    MentorshipContentKindId,
    empty_mentorship_ledger,
    form_or_reinforce_mentorship_bond,
    mentorship_partner_bias_futures,
)
from agents.models import AgentId
from simulation.runner_models import MentorshipPartnerBias

_LOG = logging.getLogger("tests.mentorship_partner_bias")


def test_prefer_bonded_adds_float_bias(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=prefer_bonded_float_bias")
    owner = AgentId("bob")
    ledger = form_or_reinforce_mentorship_bond(
        empty_mentorship_ledger(owner),
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        tick=1,
        successful_act_count=2,
        projected_trust=0.8,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
        initial_strength=0.5,
    )
    futures = (
        SimpleNamespace(
            future_id="f-bond",
            direction=SimpleNamespace(value="communicate"),
            target_agent_id=AgentId("alice"),
        ),
        SimpleNamespace(
            future_id="f-other",
            direction=SimpleNamespace(value="communicate"),
            target_agent_id=AgentId("carol"),
        ),
        SimpleNamespace(
            future_id="f-move",
            direction=SimpleNamespace(value="move"),
            target_agent_id=AgentId("alice"),
        ),
    )
    bias = MentorshipPartnerBias(
        mode="prefer_bonded",
        communicate_weight=0.25,
        content_kind_affinity=True,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        weights = mentorship_partner_bias_futures(
            ledger=ledger, partner_bias=bias, futures=futures
        )
    assert "f-bond" in weights
    assert weights["f-bond"] > 0.0
    assert "f-other" not in weights
    assert "f-move" not in weights
    assert "bond_prefer" in caplog.text


def test_ignore_mode_passthrough() -> None:
    _LOG.debug("case_id=ignore_mode_passthrough")
    owner = AgentId("bob")
    ledger = form_or_reinforce_mentorship_bond(
        empty_mentorship_ledger(owner),
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.WARNINGS,),
        tick=1,
        successful_act_count=2,
        projected_trust=0.9,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
    )
    futures = (
        SimpleNamespace(
            future_id="f1",
            direction=SimpleNamespace(value="communicate"),
            target_agent_id=AgentId("alice"),
        ),
    )
    weights = mentorship_partner_bias_futures(
        ledger=ledger,
        partner_bias=MentorshipPartnerBias(mode="ignore", communicate_weight=0.5),
        futures=futures,
    )
    assert weights == {}
