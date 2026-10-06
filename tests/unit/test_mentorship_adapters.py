"""Factual / causal / vocabulary / practices / stories adapters."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.mentorship import (
    MentorshipContentKindId,
    apply_mentorship_content_kind_adapters,
    empty_mentorship_ledger,
)
from agents.models import AgentId
from simulation.runner_models import MentorshipBondPolicy, MentorshipLineagePolicy

_LOG = logging.getLogger("tests.mentorship_adapters")


def test_factual_and_causal_adapters(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=factual_causal_adapters")
    ledger = empty_mentorship_ledger(AgentId("bob"))
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        updated, audits = apply_mentorship_content_kind_adapters(
            ledger,
            enabled_content_kinds=("factual_beliefs", "causal_hypotheses"),
            tick=2,
            predictive_world_model=True,
            belief_claim_keys=(("alice", "fact:sky", "fp:sky"),),
            causal_claim_keys=(("alice", "cause:rain", "fp:rain"),),
            bond_policy=MentorshipBondPolicy(form_after_successful_acts=1),
            lineage_policy=MentorshipLineagePolicy(),
        )
    kinds = {row.content_kind for row in updated.lineage}
    assert MentorshipContentKindId.FACTUAL_BELIEFS in kinds
    assert MentorshipContentKindId.CAUSAL_HYPOTHESES in kinds
    assert audits
    assert "adapter_uptake" in caplog.text


def test_causal_skips_without_predictive_flag(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=causal_requires_flag")
    ledger = empty_mentorship_ledger(AgentId("bob"))
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        updated, _audits = apply_mentorship_content_kind_adapters(
            ledger,
            enabled_content_kinds=("causal_hypotheses",),
            tick=1,
            predictive_world_model=False,
            causal_claim_keys=(("alice", "cause:x", "fp:x"),),
            bond_policy=MentorshipBondPolicy(form_after_successful_acts=1),
            lineage_policy=MentorshipLineagePolicy(),
        )
    assert updated.lineage == ()
    assert "causal_hypotheses_requires_flag" in caplog.text


def test_vocabulary_practices_stories_mode_gates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=social_adapter_mode_gates")
    ledger = empty_mentorship_ledger(AgentId("bob"))
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.mentorship"):
        skipped, _ = apply_mentorship_content_kind_adapters(
            ledger,
            enabled_content_kinds=("vocabulary", "social_practices", "stories"),
            tick=1,
            semantic_naming_on=False,
            social_convention_on=False,
            cultural_narrative_on=False,
            naming_keys=(("alice", "vocab:a", "fp:a"),),
            convention_keys=(("alice", "practice:b", "fp:b"),),
            story_keys=(("alice", "story:c", "fp:c"),),
            bond_policy=MentorshipBondPolicy(form_after_successful_acts=1),
            lineage_policy=MentorshipLineagePolicy(),
        )
    assert skipped.lineage == ()
    assert "vocabulary_mode_off" in caplog.text
    updated, audits = apply_mentorship_content_kind_adapters(
        ledger,
        enabled_content_kinds=("vocabulary", "social_practices", "stories"),
        tick=2,
        semantic_naming_on=True,
        social_convention_on=True,
        cultural_narrative_on=True,
        naming_keys=(("alice", "vocab:a", "fp:a"),),
        convention_keys=(("alice", "practice:b", "fp:b"),),
        story_keys=(("alice", "story:c", "fp:c"),),
        bond_policy=MentorshipBondPolicy(form_after_successful_acts=1),
        lineage_policy=MentorshipLineagePolicy(),
    )
    kinds = {row.content_kind for row in updated.lineage}
    assert MentorshipContentKindId.VOCABULARY in kinds
    assert MentorshipContentKindId.SOCIAL_PRACTICES in kinds
    assert MentorshipContentKindId.STORIES in kinds
    assert len(audits) == 3
