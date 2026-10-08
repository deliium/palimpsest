"""Unit tests for blank-slate subjective-copy deny-list guards."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)

_LOG = logging.getLogger("tests.new_agent_blank_slate_guard")


def test_deny_list_covers_locked_stores() -> None:
    _LOG.debug("case_id=deny_list_covers_locked_stores")
    required = {
        "episodic_memory",
        "semantic_beliefs",
        "self_model",
        "theory_of_mind",
        "goals",
        "cultural_narratives",
        "cognition_trace",
        "relationships",
        "semantic_naming",
        "social_norms",
        "social_conventions",
        "skill_ledger",
        "developmental_knowledge",
        "society_download",
        "culture_pack",
        "encyclopedia",
        "language_pack",
        "mentorship_bonds",
        "taught_content_lineage",
        "mentorship",
        "cultural_features",
        "practical_knowledge",
        "knowledge_ledger",
        "technique_pack",
        "knowledge_pack",
        "parent_technique_copy",
        "knowledge_genealogy",
        "experiment_ledger",
    }
    assert required.issubset(SUBJECTIVE_COPY_DENY_LIST)
    assert tuple(BLANK_SLATE_SUBJECTIVE_STORES) == (
        "episodic_memory",
        "semantic_beliefs",
        "self_model",
        "theory_of_mind",
        "goals",
        "cultural_narratives",
        "cognition_trace",
        "relationships",
        "semantic_naming",
        "social_norms",
        "social_conventions",
        "skill_ledger",
        "developmental_knowledge",
        "mentorship_bonds",
        "taught_content_lineage",
        "cultural_features",
        "practical_knowledge",
        "experiment_ledger",
    )


def test_assert_blank_slate_passes_when_empty() -> None:
    _LOG.debug("case_id=assert_blank_slate_passes_when_empty")
    assert_blank_slate_subjective_state(
        AgentId("entrant-1"), BlankSlateStoreCounts()
    )


def test_assert_blank_slate_fails_on_content() -> None:
    _LOG.debug("case_id=assert_blank_slate_fails_on_content")
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-1"),
            BlankSlateStoreCounts(episodic_memory=1),
        )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-1"),
            BlankSlateStoreCounts(skill_ledger=2, relationships=1),
        )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-1"),
            BlankSlateStoreCounts(practical_knowledge=1),
        )
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            AgentId("entrant-1"),
            BlankSlateStoreCounts(experiment_ledger=1),
        )
