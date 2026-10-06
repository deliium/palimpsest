"""Practical skills / recipes / warnings uptake from teaching advice."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition.mentorship import (
    MentorshipContentKindId,
    apply_mentorship_from_teaching,
    empty_mentorship_ledger,
)
from agents.models import AgentId
from simulation.runner_models import MentorshipBondPolicy, MentorshipLineagePolicy

_LOG = logging.getLogger("tests.mentorship_teaching_uptake")


def test_teaching_advice_records_skills_recipes_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=teaching_uptake_content_kinds")
    owner = AgentId("bob")
    ledger = empty_mentorship_ledger(owner)
    advice = (
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="foraging"),
            act=SimpleNamespace(value="explain"),
            occurrence_id="occ-1",
            band=SimpleNamespace(value="high"),
        ),
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="crafting"),
            act=SimpleNamespace(value="demonstrate"),
            occurrence_id="occ-2",
            band=SimpleNamespace(value="mid"),
        ),
        SimpleNamespace(
            source_agent_id=AgentId("alice"),
            domain=SimpleNamespace(value="healing"),
            act=SimpleNamespace(value="explain"),
            occurrence_id="occ-3",
            band=SimpleNamespace(value="low"),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        updated, audits = apply_mentorship_from_teaching(
            ledger,
            enabled_content_kinds=(
                "practical_skills",
                "production_recipes",
                "warnings",
            ),
            advice_delta=advice,
            tick=3,
            bond_policy=MentorshipBondPolicy(form_after_successful_acts=1, min_trust=0.1),
            lineage_policy=MentorshipLineagePolicy(),
        )
    kinds = {entry.content_kind for entry in updated.lineage}
    assert MentorshipContentKindId.PRACTICAL_SKILLS in kinds
    assert MentorshipContentKindId.PRODUCTION_RECIPES in kinds
    assert MentorshipContentKindId.WARNINGS in kinds
    assert updated.bonds
    assert audits
    assert "uptake_recorded" in caplog.text
    # No teacher competence levels copied into learner ledger.
    assert all(
        getattr(entry, "believed_level", None) is None for entry in updated.lineage
    )
